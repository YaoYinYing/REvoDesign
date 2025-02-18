
from typing import Dict
from REvoDesign.Qt import QtWidgets

from REvoDesign.basic import SingletonAbstract


class TaskBoard(SingletonAbstract):
    def singleton_init(self, *args, **kwargs):
        self.tasks: Dict
        ...


class TaskPanel(QtWidgets.QWidget): # type: ignore
    def __init__(self, *args, **kwargs):
        