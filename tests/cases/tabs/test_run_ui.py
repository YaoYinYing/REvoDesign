import os

import pytest

from ...conftest import TestWorker

os.environ["PYTEST_QT_API"] = "pyqt5"


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(self, test_worker: TestWorker):
        test_worker.test_id = test_worker.method_name()
        # Check if the main window of the plugin is visible
        assert test_worker.plugin.window.isVisible()
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        for tab in test_worker.tab_widget_mapping.keys():
            test_worker.go_to_tab(tab_name=tab)
            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"test_tab_{tab}",
            )



class TestNonEnglishInput:
    @pytest.mark.parametrize('filename',[
        'my_project_mutant.txt',
        '我的项目_mutant.txt',
        '我的项目 mutant.txt',

    ])
    @pytest.mark.parametrize('lan, non_eng_dirname',[
        ('english', 'a strange directory name'),
        ('korean', '이건 좀 애매한 디렉토리명'),
        ('french', 'ceci est un nom de dossier étrange'),
        ('spanish', 'esto es un nombre de carpeta extraño'),
        ('german', 'dies ist ein seltsamer Ordner'),
        ('italian', 'questo è un nome di cartella strano'),
        ('portuguese', 'isto é um nome de pasta estranho'),
        ('japanese', 'これは奇妙なフォルダ名です'),
        ('chinese', '这是一个非常奇怪的 文件夹名'),
        ('russian', 'это странное название папки'),
        ('polish', 'to jest bardzo nietypowe nazwy katalogu'),
        ('hindi', 'यह एक बिल्कुल नाम है'),
        ('tamil', 'இந்த ஒருகோரியாகவும் பெயர்'),
        ('chinese_traditional', '這是一個非常奇怪的文件夾名'),
        ('mixed_chinese_english', '这是一个非常奇怪的dirname'),
        ('mixed_chinese_english_with_space', '这是一个非常奇怪的 dirname'),
    ])
    @pytest.mark.parametrize('drop_space_with_underline', [True, False])
    def test_non_english_input(self, drop_space_with_underline, lan, non_eng_dirname,filename, test_worker: TestWorker, test_tmp_dir):
        test_worker.test_id= test_worker.method_name()
        # test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='visualize')
        non_eng_dirname=non_eng_dirname.replace(' ', '_') if drop_space_with_underline else non_eng_dirname

        expected_input_save_path= os.path.join(test_tmp_dir, non_eng_dirname, filename)

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            expected_input_save_path,
        )
        input_save_path_cfg=test_worker.plugin.bus.get_value('ui.visualize.input.from_mutant_txt', reject_none=True)

        base_name=f'{lan}_{non_eng_dirname.replace(" ", "_")}{drop_space_with_underline}_{filename}'
        test_worker.save_screenshot(widget=test_worker.plugin.window,
                                    basename=base_name)
        
        test_worker.save_new_experiment(base_name)

        assert input_save_path_cfg is not None
        assert input_save_path_cfg == expected_input_save_path
        assert non_eng_dirname in expected_input_save_path
        assert non_eng_dirname in input_save_path_cfg
        