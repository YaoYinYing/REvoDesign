# Application Layer

## Menu Builders

The menu system uses builder functions that generate `MenuItem` tuples on demand.
Filesystem scanning (for config-edit and recent-experiment links) is deferred until
the builder is called — importing the module is cheap.

::: REvoDesign.application.menu.core_menu_links
    options:
      show_submodules: false

::: REvoDesign.application.menu.menu_links
    options:
      show_submodules: false

::: REvoDesign.application.menu.config_edit_links
    options:
      show_submodules: false

::: REvoDesign.application.menu.static_menu_links
    options:
      show_submodules: false

::: REvoDesign.application.menu.TOOLS_MENU_LINKS
    options:
      show_submodules: false

## Icon Setter

::: REvoDesign.application.icon.IconSetter
    options:
      show_submodules: false

## Cluster Tab Controller

::: REvoDesign.application.cluster_tab.ClusterTabController
    options:
      show_submodules: false

## Internationalization

::: REvoDesign.application.i18n.language_settings.LanguageSwitch
    options:
      show_submodules: false

::: REvoDesign.application.i18n.language_settings.LanguageItem
    options:
      show_submodules: false

::: REvoDesign.application.i18n.language_settings.LanguageNameRegistry
    options:
      show_submodules: false
