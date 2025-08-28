class BaseLLM:
    name = "base"

    def generate(self, prompt: str, **kw) -> dict:
        raise NotImplementedError
