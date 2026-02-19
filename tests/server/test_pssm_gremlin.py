# TODO: create comprehensive integration tests for PSSM GREMLIN runner image and server image
# - runner tests
# 0. ensure the miniuc databases is generated as described in the tests/data/msa/README.md, at conftest.py
# 1. build the runner image (see server/docker/runner/Dockerfile)
# 2. run the image via docker (see server/docker/run_docker.py, use  miniuc databases)
# - server tests
# 0. build the server image (see server/docker/server/Dockerfile)
# 1. run the server instance by docker compose (see server/docker-compose.yml, use  miniuc databases)
# 2. test the server instance by requesting the server's API and urls
# - Note
# 1. to avoid conflicts between the production and testing runner/server, we should use different ports (server, redis, etc.) and image names (suffix as `_test`, for example) for testing
# 2. clean up the testing containers and images after testing
# 3. for testing basic auth, use `test_username` and `test_password_<randomized 256 bit hex>` and store the test credentials in the server's configuration file under the workdir/server_test/users.txt
