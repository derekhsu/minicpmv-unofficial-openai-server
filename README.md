# python-minicpmv-xpv

## Introduction

This is an unofficial project providing an OpenAI compatibable Restful API server based on FastAPI for [MiniCPM-V](https://github.com/OpenBMB/MiniCPM-V) multimodal LLMs (MLLMs).

## Usage 

### Run this project

1. Clone this project.
2. In the root directory of the project, run `uvicorn app.main:app --port 5000 --host 0.0.0.0`.
3. You can run this API using gunicorn or other similiar tools.

#### Run behind proxy

If your service runs behind a proxy, set the environment variable `ROOT_PATH` to the rewritten URL to display `/docs` and `/redoc` correctly, such as:

```shell
ROOT_PATH=/mllm uvicorn app.main:app --port 5000 --host 0.0.0.0
```

### Call from LangChain OpenAI client

```python
return ChatOpenAI(
    model="model_name", # Not important
    openai_api_key="EMPTY",
    openai_api_base="http://", # Your API address
    verbose=verbose,
    streaming=streaming,
    temperature=temperature,
    max_tokens=max_tokens,
    callbacks=callbacks
)
```            
