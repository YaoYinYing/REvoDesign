from ..tools.customized_widgets import AskedValue, AskedValueCollection, ask_for_values, ask_for_appendable_values


from .shortcuts import dump_sidechains


def menu_dump_sidechains() -> None:
    values = ask_for_values(
        "Dump sidechains",
        AskedValueCollection(
            [
                AskedValue("sele", reason="Select the models to dump sidechains."),
                AskedValue("enabled_only",False, typing=bool, reason= "Dump only enabled models."),
                AskedValue("save_dir","png/sidechains", reason="Directory to save the sidechains."),
                AskedValue("height",1280,typing=int, reason="Height of the image."),
                AskedValue("width",1280,typing=int, reason="Width of the image."),
                AskedValue("dpi",150,typing=int, reason="DPI of the image."),
                AskedValue("ray",True,typing=bool, reason="Use ray to dump sidechains.")
            ]
        )
    )

    if not values:
        return

    dump_sidechains(**values.asdict)