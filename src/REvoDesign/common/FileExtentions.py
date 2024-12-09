'''
File extensions used in REvoDesign
'''
from ..basic import FileExtension as Ext
from ..basic import FileExtensionCollection as ExtColl

Session = ExtColl(
    (
        Ext("pze", "Compressed PyMOL Session"),
        Ext("pse", "PyMOL Session"),
    ),
)
Mutable = ExtColl(
    (
        Ext("txt", "Text file"),
        Ext("mut.txt", "Text file"),
        Ext("csv", "CSV file"),
        Ext("tsv", "TSV file"),
        Ext("xlsx", "Microsoft Excel (modern) file"),
        Ext("xls", "Microsoft Excel (legacy) file"),
    )

)
PDB = ExtColl(
    (
        Ext("pdb", "Protein Data Bank format file"),
        Ext("ent", "Protein Data Bank format file"),
        Ext("cif", "Crystallographic Information File"),
        Ext("mmcif", "Macromolecular Crystallographic Information File"),
    )
)
MOL = ExtColl(
    (
        Ext("mol", "Mol2 file"),
        Ext("sdf", "SDF file"),
    )
)

PSSM = ExtColl(
    (
        Ext("csv", "CSV file"),
        Ext("pssm", "Raw PSSM file"),
    )
)
MSA = ExtColl(
    (
        Ext("fas", "MSA in FASTA"),
        Ext("fasta", "MSA in FASTA"),
        Ext("a3m", "MSA in A3M from HH-suite"),
    )
)
TXT = ExtColl(
    (
        Ext("txt", "Text file"),
    )
)

# a hack of file extension filter, to enable those without explicit extension
Any = ExtColl(
    (
        Ext("* *", "Any file"),
    )
)
Compressed = ExtColl(
    (
        Ext("zip", "ZIP archive"),
        Ext("tar.gz", "Tarball (TAR.GZ)"),
        Ext("tgz", "Tarball (TGZ)"),
        Ext("tar.bz2", "Tarball (TAR.BZ2)"),
        Ext("tbz", "Tarball (TBZ)"),
        Ext("tar.xz", "Tarball (TAR.XZ)"),
    )
)
PickledObject = ExtColl(
    (
        Ext("pkl", "Dumpped Pickle Object"),
    )
)
YAML = ExtColl(
    (
        Ext("yaml", "Config file in YAML"),
    )
)

JSON= ExtColl(
    (
        Ext("json", "JSON file"),
    )
)
