# How to Add a New Mutagenesis Profile Format

This guide explains how to add support for a new profile format (PSSM, CSV, TSV,
etc.) to REvoDesign. Profile parsers convert mutagenesis profile files into a
standard `pandas.DataFrame` used downstream for design and visualization.

## 1. Subclass `ProfileParserAbstract`

The base class lives in `REvoDesign.common.profile_parsers`. Create a new file
alongside the existing parsers, or add your class directly into
`profile_parsers.py`.

```python
from REvoDesign.common.profile_parsers import ProfileParserAbstract


class MyFormatParser(ProfileParserAbstract):
    name = "MyFormat"
    prefer_lower = False  # True if lower scores are better (e.g. ddG)
```

## 2. Set the `name` attribute

The `name` string is used by `ProfileManager` to look up your parser at runtime
when a user selects the format from the dropdown:

```python
# REvoDesign/common/profile_parsers.py, ProfileManager._initialize_parser
parser_class = [parser for parser in ALL_PARSER_CLASSES if parser.name == self.profile_type][0]
```

The name will also appear automatically in the **Profile Type** combo boxes on
the Mutate and Visualize tabs via
`CallableGroupValues.list_all_profile_parsers()`.

## 3. Implement `parse()`

Your `parse()` method must return a `pandas.DataFrame` whose columns are
residue positions (0-indexed strings like `"0"`, `"1"`, ...; the existing
`PSSM_Parser` uses 1-indexed columns) and whose rows
are the 20 standard amino acids in alphabetical order by one-letter code:

```python
    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f"Profile {self.profile_input} does not exist."
            )

        # Your parsing logic here:
        self.df = pd.read_csv(self.profile_input, ...)
        # Ensure columns are string residue indices starting at "0"
        self.df.columns = [str(i) for i in range(len(self.df.columns))]
        return self.df
```

The base class provides several properties you can use or override:

| Property               | Description                                    |
|------------------------|------------------------------------------------|
| `is_valid_profile`     | Whether the input file exists                  |
| `profile_input_bn`     | Basename of the input file                     |
| `score_max_abs`        | Max absolute value across the DataFrame        |
| `min_score_profile`    | `-score_max_abs`                               |
| `max_score_profile`    | `+score_max_abs`                               |

## 4. Register in `ALL_PARSER_CLASSES`

Open `REvoDesign/common/profile_parsers.py` and add your class to the
`ALL_PARSER_CLASSES` tuple at the bottom of the file:

```python
ALL_PARSER_CLASSES = (
    PSSM_Parser,
    CSVProfileParser,
    TSVProfileParser,
    MyFormatParser,         # <-- add yours
)
```

This is the only registration step required. The tuple is consumed by
`ProfileManager` (for runtime dispatch) and by
`CallableGroupValues.list_all_profile_parsers()` (for populating UI combo
boxes). There is no separate plugin registry or decorator needed for parsers.

## 5. Verify

Run the parser-related tests to confirm nothing is broken:

```bash
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW="profile or parser"
```
