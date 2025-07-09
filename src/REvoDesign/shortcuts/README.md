# **How to Develop a Function into a Window Pop-up in REvoDesign**

### **Overview**

In REvoDesign, converting a function into a **window pop-up** means creating a dynamic user interface (UI) that collects user input before running the function. This is achieved by using the **dialog wrapper system**, where you define the window layout and logic in a YAML configuration and link it to the function. This allows you to display a pop-up dialog, collect inputs dynamically, and then pass them to the function for execution.

### **Steps to Convert a Function into a Window Pop-up**

The process involves the following steps:

1. **Define the Function's Parameters and Logic**
2. **Create the Dialog UI Configuration (in YAML)**
3. **Register the Function and Dialog UI**
4. **Run the Dialog with Dynamic Values**

### **1. Define the Function's Parameters and Logic**

First, you need a function that will be triggered by the dialog. This function typically accepts parameters and performs some task. For example, a function that performs RosettaLigand docking:

```python
def wrapped_rosettaligand(**kwargs):
    """
    Runs the RosettaLigand docking.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    # Parse ligand params
    ligand_params: str = kwargs.pop('ligand_params')
    ligands = ligand_params.split('|')
    kwargs['ligands'] = ligands

    # Parse start_from_xyz_sele to start_from_xyz coordinates
    start_from_xyz_sele = kwargs.pop('start_from_xyz_sele')
    if not start_from_xyz_sele:
        kwargs['start_from_xyz'] = None
    else:
        kwargs['start_from_xyz'] = tuple(cmd.centerofmass(start_from_xyz_sele))

    # Call the actual RosettaLigand function
    shortcut_rosettaligand(**kwargs)
```

In this example, the function `wrapped_rosettaligand` accepts parameters like `ligand_params`, `start_from_xyz_sele`, and others, which will be collected from the dialog.

### **2. Create the Dialog UI Configuration (in YAML)**

In REvoDesign, the dialog UI configuration is typically defined in a **YAML** file, which describes the fields and layout of the pop-up window. Each field corresponds to a parameter in your function. Here's an example configuration for `wrapped_rosettaligand`:

```yaml
wrapped_rosettaligand:
  title: "RosettaLigand"
  banner: "Perform RosettaLigand Docking"
  options:
    - name: "pdb"
      type: str
      reason: "Path to the PDB file"
      source: "File"
      required: true
      ext: "PDB_STRICT"
    - name: "ligand_params"
      type: str
      reason: "Path to the ligands (*.params) to be docked."
      source: "Files"
      required: true
      ext: "RosettaParams"
    - name: "nstruct"
      type: int
      default: 10
      reason: "Number of structures to be generated."
      required: true
    - name: "chain_id_for_dock"
      type: str
      default: "B"
      reason: "Chain ID for the docking."
      required: true
    - name: "save_dir"
      type: str
      default: ""
      reason: "Path to the directory to save the results."
      source:
```
