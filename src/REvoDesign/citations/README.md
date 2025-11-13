# Citation Module

This module provides a citation annotation for any necessary classes, methods, and functions.

## CitableModuleAbstract Class

This class is the base class for all citable modules.
It provides a `__bibtex__` property and a `self.cite()` method to perform citation operations.
The `self.cite()` method will print the citation note to the console and add it to the citation note, so that user can cite the module in their own work.

## Basic Usage

```python
# A citable module
class MyClass(CitableModuleAbstract):
    __bibtex__: dict[str, Union[str, tuple]] = {
        'Awesome Tool': """@article{Awesome Tool, ...}"""
    }
    def __init__(self):
        ...
    
    def run_method(self):
        ...
        self.cite()

my_class = MyClass()
my_class.run_method() # a citation note will be printed

```

## Use `get_cited` to handle citation of any function automatically

The `get_cited` decorator can be used to automatically cite a function. It simply wraps the function, run the function, search for the `__bibtex__` citation note and adds it to the citation manager. This is useful when you want to cite a function that is called by another function.

### Cite a class object method

```python
class MyClass:

    __bibtex__: dict[str, Union[str, tuple]] = {'Awesome Tool': """@article{Awesome Tool, ...}"""}

    @get_cited
    def my_method(self):
        print('I am a class object method.')


my_class = MyClass()
# citation will automatically be printed and added to 
# the citation note after the function is called
my_class.my_method() 
```

### Cite a classmethod or a staticmethod

One can use `get_cited` to cite classmethod or staticmethod.
Please note that the order of decoration matters. The `get_cited` decorator must be placed before (which means at the **bottom** of) the classmethod or staticmethod decorator.

```python
class MyClass:
    __bibtex__: dict[str, Union[str, tuple]] = {'Awesome Tool': """@article{Awesome Tool, ...}"""
}
    @classmethod
    @get_cited
    def my_classmethod(cls, *args, **kwargs):
        print('I am a classmethod.')

    @staticmethod
    @get_cited
    def my_staticmethod(*args, **kwargs):
        print('I am a staticmethod.')
    
    
my_class = MyClass()
my_class.my_classmethod()
my_class.my_staticmethod()
```

### Cite a function

As the decorator returns a function w/ exactly the same name yet different from the original function, one must add the citation note to the function as `<function>.__bibtex__` manually. After that, use `get_cited` to generate a citable function wrapper.


Here is an real case we are using in REvoDesign:

```python

# adapted from pymol script loadBfacts.py
# https://wiki.pymol.org/index.php/Load_new_B-factors
# Gatti-Lafranconi, Pietro (2014). Pymol script: loadBfacts.py. figshare.
# Software. https://doi.org/10.6084/m9.figshare.1176991.v1


# 1. citation note
load_b_factors_citation : dict[str, Union[str, tuple]] = {
    'loadBfacts.py': """@article{Gatti-Lafranconi2014,
author = "Pietro Gatti-Lafranconi",
title = "{Pymol script: loadBfacts.py}",
year = "2014",
month = "9",
url = "https://figshare.com/articles/software/Pymol_script_loadBfacts_py/1176991",
doi = "10.6084/m9.figshare.1176991.v1"
}"""
}

# 2. write a function needed to be cited
def _load_b_factors(
        mol: str,
        chain_ids: str,
        keep_missing: bool,
        source: str,
        label: Optional[str] = None,
        pos_slice: Optional[str] = None,
        offset: int = 0,
        visual: bool = True) -> None:
    print('I load the B-factors to a struture.')


# 3. add citation note to the function as `<function>.__bibtex__`
setattr(_load_b_factors, '__bibtex__', load_b_factors_citation)

# 4. generate a citable function wrapper. Only the wrapper is called can the citation note be added.
load_b_factors=get_cited(_load_b_factors)
```


## Troubleshooting

1. Please DO avoid citing class that in a private scope (inside a function, etc.), as solving the parent class from the method is hard. This means that all citable classes/functions must be visible from public scope (importable to other modules).
2. The current class solving and method guessing mechanism is not perfect and far to complicated. It may fit the most cases, but it is not guaranteed to work for all, unless you know what you are doing.
