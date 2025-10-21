# Containerised Reproduction

Build the Docker image and run the evaluation pipeline end-to-end:

```bash
cd docker
docker build -t k8s-auto-fix .
docker run --rm -it \
  -v $(pwd)/..:/workspace \
  k8s-auto-fix \
  bash -lc "cd /workspace && make reproducible-report"
```

The image ships with Python 3.12 and the pinned dependencies from `requirements.txt`; mounting the repo keeps artefact outputs on the host machine.
