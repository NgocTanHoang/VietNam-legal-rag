from abc import ABC, abstractmethod
from typing import Any

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, source: Any) -> Any:
        """Phương thức trích xuất dữ liệu từ nguồn (Parquet, PDF, v.v.)"""
        pass
