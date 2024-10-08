import os
import numpy as np
import torch
import json
from PIL import Image
import base64
import io
from accelerate import load_checkpoint_and_dispatch, init_empty_weights
from transformers import AutoTokenizer, AutoModel

from app.api.v1.models.chat_completions import ChatCompletionsRequest, ChatMessage

from .omnilmm.utils import disable_torch_init
from .omnilmm.model.omnilmm import OmniLMMForCausalLM
from .omnilmm.model.utils import build_transform
from .omnilmm.train.train_utils import omni_preprocess

import logging

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_TOKEN = "<image>"
DEFAULT_IMAGE_PATCH_TOKEN = "<im_patch>"
DEFAULT_IM_START_TOKEN = "<im_start>"
DEFAULT_IM_END_TOKEN = "<im_end>"

    

def init_omni_lmm(model_path):
    torch.backends.cuda.matmul.allow_tf32 = True
    disable_torch_init()
    model_name = os.path.expanduser(model_path)
    print(f'Load omni_lmm model and tokenizer from {model_name}')
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, model_max_length=2048)

    if False:
        # model on multiple devices for small size gpu memory (Nvidia 3090 24G x2) 
        with init_empty_weights():
            model = OmniLMMForCausalLM.from_pretrained(model_name, tune_clip=True, torch_dtype=torch.bfloat16)
        model = load_checkpoint_and_dispatch(model, model_name, dtype=torch.bfloat16, 
                    device_map="auto",  no_split_module_classes=['Eva','MistralDecoderLayer', 'ModuleList', 'Resampler']
        )
    else:
        model = OmniLMMForCausalLM.from_pretrained(
            model_name, tune_clip=True, torch_dtype=torch.bfloat16
        ).to(device='cuda', dtype=torch.bfloat16)

    image_processor = build_transform(
        is_train=False, input_size=model.model.config.image_size, std_mode='OPENAI_CLIP')

    mm_use_im_start_end = getattr(model.config, "mm_use_im_start_end", False)
    assert mm_use_im_start_end

    tokenizer.add_tokens([DEFAULT_IMAGE_PATCH_TOKEN, DEFAULT_IM_START_TOKEN,
                         DEFAULT_IM_END_TOKEN], special_tokens=True)


    vision_config = model.model.vision_config
    vision_config.im_patch_token = tokenizer.convert_tokens_to_ids(
        [DEFAULT_IMAGE_PATCH_TOKEN])[0]
    vision_config.use_im_start_end = mm_use_im_start_end
    vision_config.im_start_token, vision_config.im_end_token = tokenizer.convert_tokens_to_ids(
        [DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN])
    image_token_len = model.model.config.num_query

    return model, image_processor, image_token_len, tokenizer

def expand_question_into_multimodal(question_text, image_token_len, im_st_token, im_ed_token, im_patch_token):
    if '<image>' in question_text[0]['content']:
        question_text[0]['content'] = question_text[0]['content'].replace(
            '<image>', im_st_token + im_patch_token * image_token_len + im_ed_token)
    else:
        question_text[0]['content'] = im_st_token + im_patch_token * \
            image_token_len + im_ed_token + '\n' + question_text[0]['content']
    return question_text

def wrap_question_for_omni_lmm(question, image_token_len, tokenizer):
    question = expand_question_into_multimodal(
        question, image_token_len, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN, DEFAULT_IMAGE_PATCH_TOKEN)

    conversation = question
    data_dict = omni_preprocess(sources=[conversation],
                                  tokenizer=tokenizer,
                                  generation=True)

    data_dict = dict(input_ids=data_dict["input_ids"][0],
                     labels=data_dict["labels"][0])
    return data_dict



class OmniLMM12B:
    def __init__(self, model_path) -> None:
        model, img_processor, image_token_len, tokenizer = init_omni_lmm(model_path)
        self.model = model
        self.image_token_len = image_token_len
        self.image_transform = img_processor
        self.tokenizer = tokenizer
        self.model.eval()

    def decode(self, image, input_ids):
        with torch.inference_mode():
            output = self.model.generate_vllm(
                input_ids=input_ids.unsqueeze(0).cuda(),
                images=image.unsqueeze(0).half().cuda(),
                temperature=0.6,
                max_new_tokens=1024,
                # num_beams=num_beams,
                do_sample=True,
                output_scores=True,
                return_dict_in_generate=True,
                repetition_penalty=1.1,
                top_k=30,
                top_p=0.9,
            )

            response = self.tokenizer.decode(
                output.sequences[0], skip_special_tokens=True)
            response = response.strip()
            return response

    def chat(self, input):
        try:
            image = Image.open(io.BytesIO(base64.b64decode(input['image']))).convert('RGB')
        except Exception as e:
            return "Image decode error"

        msgs = json.loads(input['question'])
        input_ids = wrap_question_for_omni_lmm(
            msgs, self.image_token_len, self.tokenizer)['input_ids']
        input_ids = torch.as_tensor(input_ids)
        #print('input_ids', input_ids)
        image = self.image_transform(image)

        out = self.decode(image, input_ids)

        return out
        

def img2base64(file_name):
    with open(file_name, 'rb') as f:
        encoded_string = base64.b64encode(f.read())
        return encoded_string
    
def _create_blank_image():
    # Assuming a size of 224x224 with 448 channels, modify as needed
    blank_image = Image.new('RGB', (100, 100), (255, 255, 255))  # White 100x100 image
    return blank_image

class MiniCPMV:
    def __init__(self, model_path) -> None:
        self.model = AutoModel.from_pretrained(model_path, trust_remote_code=True).to(dtype=torch.bfloat16)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model.eval().cuda()

    def chat(self, input):
        try:            
            image = Image.open(io.BytesIO(base64.b64decode(input['image']))).convert('RGB')
        except Exception as e:
            return "Image decode error"

        msgs = json.loads(input['question'])
        
        answer, context, _ = self.model.chat(
            image=image,
            msgs=msgs,
            context=None,
            tokenizer=self.tokenizer,
            sampling=True,
            temperature=0.7
    	)
        return answer

class MiniCPMV2_5:
    def __init__(self, model_path) -> None:
        self.model = AutoModel.from_pretrained(model_path, trust_remote_code=True).to(dtype=torch.float16)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model.eval().cuda()

    def chat(self, input: ChatCompletionsRequest):
        # try:            
        #     image = Image.open(io.BytesIO(base64.b64decode(input.image))).convert('RGB')
        # except Exception as e:
        #     logger.error(f"Image decode error: {e}") 
        logger.info(f"request: {input}")

        processed_messages = []
        has_image_in_all_messages = False

        # First pass to check if any image exists
        for message in input.messages:
            if message.role == "user" and isinstance(message.content, list):
                for item in message.content:
                    if isinstance(item, dict) and item.get('type') == "image_url":
                        has_image_in_all_messages = True
                        break
            if has_image_in_all_messages:
                break
        
        logger.info(f"has_image_in_all_messages: {has_image_in_all_messages}")
        user_message_index = None
        for idx, message in enumerate(input.messages):
            if message.role == "user":
                if user_message_index is None:
                    user_message_index = idx
                if isinstance(message.content, str):
                    processed_messages.append({"role": "user", "content": message.content})
                elif isinstance(message.content, list):
                    processed_content = []
                    for item in message.content:
                        if isinstance(item, dict) and 'type' in item:                            
                            if item['type'] == "text":
                                processed_content.append(item['text'])                                    
                            elif item['type'] == "image_url":
                                image_url = item['image_url']
                                if 'url' in image_url:
                                    url = image_url['url']
                                    splitted_url = url.split(',', 1)
                                    if splitted_url[0].startswith("data:image/"):
                                        image = Image.open(io.BytesIO(base64.b64decode(splitted_url[1]))).convert('RGB')
                                        processed_content.append(image)
                    processed_messages.append({"role": "user", "content": processed_content})
            else:
                processed_messages.append({"role": message.role, "content": message.content})

        # If no image in all messages, add a blank image to the first user message
        if not has_image_in_all_messages and user_message_index is not None:
            blank_image = _create_blank_image()
            if isinstance(processed_messages[0]["content"], list):
                processed_messages[user_message_index]["content"].append(blank_image)
            else:
                processed_messages[user_message_index]["content"] = [processed_messages[user_message_index]["content"], blank_image]

        logger.info(f"processed_message: {processed_messages}")
        if processed_messages[0]['role'] == "system":
            system_prompt = processed_messages[0]['content']
            processed_messages = processed_messages[1:]
        else:
            system_prompt = ''
    
        #msgs = json.dumps([message.dict() for message in processed_messages])
        
        logger.info(f"system_prompt: {system_prompt}")

        answer = self.model.chat(
            image=None,
            msgs=processed_messages,
            tokenizer=self.tokenizer,
            sampling=True,
            max_new_tokens=input.max_tokens,
            temperature=input.temperature,
            repetition_penalty=input.repetition_penalty,
            stream=input.stream,
            system_prompt=system_prompt
    	)
        return answer


class MiniCPMVChat:
    def __init__(self, model_path) -> None:
        if '12B' in model_path:
            self.model = OmniLMM12B(model_path)
        elif 'MiniCPM-Llama3-V' in model_path:
            self.model = MiniCPMV2_5(model_path)
        else:
            self.model = MiniCPMV(model_path)

    def chat(self, input):
        return self.model.chat(input)


if __name__ == '__main__':
    
    model_path = 'openbmb/OmniLMM-12B'
    chat_model = MiniCPMVChat(model_path)

    im_64 = img2base64('./assets/worldmap_ck.jpg')

    # first round chat 
    msgs = [{"role": "user", "content": "What is interesting about this image?"}]
    input = {"image": im_64, "question": json.dumps(msgs, ensure_ascii=True)}
    answer = chat_model.chat(input)
    print(msgs[-1]["content"]+'\n', answer)

    # second round chat 
    msgs.append({"role": "assistant", "content": answer})
    msgs.append({"role": "user", "content": "Where is China in the image"})
    input = {"image": im_64,"question": json.dumps(msgs, ensure_ascii=True)}
    answer = chat_model.chat(input)
    print(msgs[-1]["content"]+'\n', answer)
