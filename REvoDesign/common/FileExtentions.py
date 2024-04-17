from immutabledict import immutabledict
from dataclasses import dataclass


@dataclass(frozen=True)
class REvoDesignFileExtentions:
    Session: immutabledict = immutabledict(
        {
            'pze': 'PZE file',
            'pse': 'PSE file',
        }
    )

    Mutable: immutabledict = immutabledict(
        {
            'txt': 'Mutagenesis table file',
            'mut.txt': 'Mutagenesis table file',
            'csv': 'Scored Mutagenesis table file',
            'tsv': 'Scored Mutagenesis table file',
            'xlsx': 'Scored Mutagenesis table file',
            'xls': 'Scored Mutagenesis table file',
        }
    )
    PDB: immutabledict = immutabledict({'pdb': 'PDB File'})

    PSSM: immutabledict = immutabledict(
        {'csv': "CSV file", 'pssm': "Raw PSSM file"}
    )

    TXT: immutabledict = immutabledict({'txt': 'TXT'})

    # a hack of file extension filter, to enable those without explicit extension
    Any: immutabledict = immutabledict({'* *': 'Any file'})

    Compressed: immutabledict = immutabledict(
        {
            'zip': "ZIP archive",
            'tar.gz': "Tarball (TAR.GZ)",
            'tgz': "Tarball (TGZ)",
            'tar.bz2': "Tarball (TAR.BZ2)",
            'tbz': "Tarball (TBZ)",
            'tar.xz': "Tarball (TAR.XZ)",
        }
    )

    PickledObject: immutabledict = immutabledict(
        {'pkl': 'Dumpped Pickle Object'}
    )

    MSA: immutabledict = immutabledict(
        {
            'fas': 'MSA in FASTA',
            'fasta': 'MSA in FASTA',
            'a3m': 'MSA in A3M from HH suite',
        }
    )

    YAML: immutabledict = immutabledict(
        {
            'yaml': 'Config file in YAML',
        }
    )
