from typing import Dict

from REvoDesign.basic import SingletonAbstract
from REvoDesign.Qt import QtWidgets


class TaskBoard(SingletonAbstract):
    def singleton_init(self, *args, **kwargs):
        self.tasks: Dict
        ...


class TaskPanel(QtWidgets.QWidget):  # type: ignore
    def __init__(self, *args, **kwargs):
