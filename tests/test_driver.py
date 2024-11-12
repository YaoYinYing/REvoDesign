from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)


def test_set_and_get_widget_value(
    mock_double_spin_box,
    mock_spin_box,
    mock_combo_box,
    mock_line_edit,
    mock_progress_bar,
    mock_lcd_number,
    mock_check_box,
):
    # Instantiate mock widgets using fixtures
    double_spin_box = mock_double_spin_box()
    spin_box = mock_spin_box()
    combo_box = mock_combo_box()
    line_edit = mock_line_edit()
    progress_bar = mock_progress_bar()
    lcd_number = mock_lcd_number()
    check_box = mock_check_box()

    # Test QDoubleSpinBox
    set_widget_value(double_spin_box, 3.14)
    assert get_widget_value(double_spin_box) == 3.14

    set_widget_value(double_spin_box, [0.0, 10.0])
    set_widget_value(double_spin_box, 5.0)
    assert get_widget_value(double_spin_box) == 5.0

    # Test QSpinBox
    set_widget_value(spin_box, 42)
    assert get_widget_value(spin_box) == 42

    set_widget_value(spin_box, [10, 50])
    set_widget_value(spin_box, 25)
    assert get_widget_value(spin_box) == 25

    # Test QComboBox with list
    set_widget_value(combo_box, ['Option 1', 'Option 2', 'Option 3'])
    set_widget_value(combo_box, 'Option 2')
    assert get_widget_value(combo_box) == 'Option 2'

    # Test QLineEdit
    set_widget_value(line_edit, 'Hello, World!')
    assert get_widget_value(line_edit) == 'Hello, World!'

    # Test QProgressBar
    set_widget_value(progress_bar, 75)
    assert get_widget_value(progress_bar) == 75

    set_widget_value(progress_bar, [0, 150])
    set_widget_value(progress_bar, 100)
    assert get_widget_value(progress_bar) == 100

    # Test QLCDNumber
    set_widget_value(lcd_number, 123.456)
    assert get_widget_value(lcd_number) == 123.456

    # Test QCheckBox
    set_widget_value(check_box, True)
    assert get_widget_value(check_box) is True

    set_widget_value(check_box, False)
    assert get_widget_value(check_box) is False

    print("All tests passed!")
