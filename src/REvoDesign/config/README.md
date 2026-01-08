# Configurations of REvoDesign and its dependencies.

```text
tree ./src/REvoDesign/config/
./src/REvoDesign/config/
├── environ.yaml ----------------------------- environment variables
├── logger.yaml ------------------------------ logging system
├── main.yaml -------------------------------- main configurations from UI and logging system
├── openmm.yaml ------------------------------ openmmsetup configurations
├── README.md -------------------------------- this readme
├── rfdiffusion ------------------------------ rfdiffusion parameter presets
│   ├── base.yaml
│   ├── enzyme.yaml
│   ├── motif_scaffoldding.yaml
│   ├── partial_diffusion.yaml
│   └── symmetry.yaml
├── rosetta-node ------------------------------ rosetta-node presets
│   ├── docker_mpi.yaml
│   ├── docker.yaml
│   ├── mpi.yaml
│   ├── native.yaml
│   ├── wsl_mpi.yaml
│   └── wsl.yaml
├── runtime.yaml
└── sidechain-solver  ------------------------- sidechain solvers
    └── pippack.yaml  ---------------------------- pippack configuration

```