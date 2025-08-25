from abc import ABC, abstractmethod
from typing import Type, TypeVar, cast
T = TypeVar('T', bound='SingletonAbstract')
class SingletonAbstract(ABC):
    _instance = None
    @classmethod
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self, *args, **kwargs):
        if not hasattr(self, "initialized"):
            self.singleton_init(*args, **kwargs)
            self.initialized = True
    @abstractmethod
    def singleton_init(self, *args, **kwargs):
    @classmethod
    def initialize(cls, *args, **kwargs):
        if not cls._instance:
            cls(*args, **kwargs)
        else:
            for key, value in kwargs.items():
                setattr(cls._instance, key, value)
    @classmethod
    def derive(cls: Type[T], name: str) -> Type[T]:
        class DerivedSingleton(cls):
            _instance = None  
            def __init__(self, *args, **kwargs):
                if not hasattr(self, 'initialized'):
                    self.singleton_init(*args, **kwargs)
                    self.initialized = True
        DerivedSingleton.__name__ = name
        return cast(Type[T], DerivedSingleton)
    @classmethod
    def reset_instance(cls):
        cls._instance = None
def reset_singletons():
    for cls in SingletonAbstract.__subclasses__():
        if hasattr(cls, '_instance') and cls._instance is not None:
            cls.reset_instance()