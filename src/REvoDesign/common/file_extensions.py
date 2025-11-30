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
PDB_STRICT = ExtColl(
    (
        Ext("pdb", "Protein Data Bank format file"),
    )
)
MOL = ExtColl(
    (
        Ext("mol", "Mol2 file"),
        Ext("sdf", "SDF file"),
    )
)

SDF = ExtColl(
    (
        Ext("sdf", "SDF file"),
    )
)

PSSM = ExtColl(
    (
        Ext("csv", "CSV file"),
        Ext("pssm", "Raw PSSM file"),
    )
)
CSV = ExtColl(
    (
        Ext("csv", "CSV file"),
    )
)
MSA = ExtColl(
    (
        Ext("fas", "MSA in FASTA"),
        Ext("fasta", "MSA in FASTA"),
        Ext("a3m", "MSA in A3M from HH-suite"),
    )
)
A3M = ExtColl(
    (
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
        Ext("txz", "Tarball (TXZ)"),
        Ext("tar", "Tarball (TAR)"),
        Ext("gz", "Compressed (GZ)"),
        Ext("bz2", "Compressed (BZ2)"),
        Ext("xz", "Compressed (XZ)"),
        Ext("rar", "RAR archive"),

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

JSON = ExtColl(
    (
        Ext("json", "JSON file"),
    )
)

RosettaParams = ExtColl(
    (
        Ext("params", "Rosetta Parameter file"),
    )
)

Pictures = ExtColl(
    (
        Ext("png", "PNG image"),
        Ext("jpg", "JPG image"),
        Ext("jpeg", "JPEG image"),
        Ext("gif", "GIF image"),
        Ext("bmp", "BMP image"),
        Ext("tiff", "TIFF image"),
        Ext("tif", "TIFF image"),
        Ext("svg", "SVG image"),
        Ext("pdf", "PDF image"),
    )
)

XvgGromacs = ExtColl(
    (
        Ext("xvg", "XVG file from Gromacs"),
    )
)
