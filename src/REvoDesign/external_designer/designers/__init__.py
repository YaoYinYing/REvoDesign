

'''
#### Hot replacement of designers ####

from REvoDesign.external_designer import EXTERNAL_DESIGNERS

if external_scorer and external_scorer in EXTERNAL_DESIGNERS:
    magician = EXTERNAL_DESIGNERS[external_scorer]
    if (
        not self.scorer  # non-scorer is set
        or magician.__name__  # a new magician is introduced here,
        != self.scorer.__class__.__name__  #  causing the class name of previous not matching that of the new one.
    ):
        logging.info(
            f'Pre-heating {external_scorer} ... This could take a while ...'
        )

        # instantialization of magician
        self.scorer = magician(
            molecule=self.design_molecule
        )
        # send initializing to progress bar.
        run_worker_thread_with_progress(
            worker_function=self.scorer.initialize,
            progress_bar=self.ui.progressBar,
        )

else:
    if self.scorer:
        logging.info(
            f'Cooling down {self.scorer.__class__.__name__} ...'
        )
    self.scorer = None


'''


from .colabdesign import ColabDesigner_MPNN

__all__ = ['ColabDesigner_MPNN']