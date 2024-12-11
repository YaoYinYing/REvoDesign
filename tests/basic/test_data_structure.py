import pytest
from REvoDesign.basic import IterableLoop


def test_initial_state():
    loop = IterableLoop(iterable=(1, 2, 3))
    assert loop.empty is False
    assert loop.initialized is False
    assert loop.current_idx == -1


def test_empty_iterable():
    loop = IterableLoop(iterable=())
    assert loop.empty is True
    assert loop.initialized is False

    with pytest.raises(IndexError):
        _ = loop.current_item


def test_pick_next():
    loop = IterableLoop(iterable=(1, 2, 3))
    assert loop.pick_next() == 0
    assert loop.current_item == 1

    loop.pick_next()
    assert loop.current_item == 2

    loop.pick_next()
    assert loop.current_item == 3

    loop.pick_next()
    assert loop.current_item == 1  # Wraps around


def test_pick_previous():
    loop = IterableLoop(iterable=(1, 2, 3))
    loop.pick_next()  # Initialize at 1
    loop.pick_next()  # Move to 2

    assert loop.pick_previous() == 0
    assert loop.current_item == 1

    loop.pick_previous()
    assert loop.current_item == 3  # Wraps around to the end


def test_walker():
    loop = IterableLoop(iterable=(1, 2, 3))
    assert loop.walker(direction=True) == 0  # Initialize and move to first item
    assert loop.current_item == 1

    loop.walker(direction=True)  # Move to next item
    assert loop.current_item == 2

    loop.walker(direction=False)  # Move to previous item
    assert loop.current_item == 1


def test_reset():
    loop = IterableLoop(iterable=(1, 2, 3))
    loop.pick_next()  # Initialize
    assert loop.current_idx == 0

    loop.reset()
    assert loop.current_idx == -1
    assert loop.initialized is False
