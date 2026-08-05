from abc import ABC, abstractmethod

class BaseLLM(ABC):
    @abstractmethod
    def invoke(self, prompt: str, system_prompt: str = "") -> str:
        """Processa o prompt e retorna a resposta do modelo."""
        pass