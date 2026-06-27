
You are building an MCP server 

Use Python with FastAPI, and any appropriate libraries.
The MCP server must support multiple, simultaneous sessions.

The MCP server must require authentication. For now, the only supported method will 
be a pre-prepared bearer token specified in .env.  Plan for adding OAuth2 support later.

The MCP server will provide AI agents with read/write access to the Ex Libris Acquisitions API, 
which is described in `acq.json` in this directory.

The entire server will be deployed under `MCP_URL` via https which is part of a
K8s cluster.  You must use namespace `vtlib`, which you should assume to exist (don't try
creating it), and you need to use the kubeconfig file `endeavour.yaml` to access it.  
Use a kustomize-style setup for your k8s/ file.
Use a configMapGenerator and a secretGenerator as appropriate; create scripting to 
derive those files' content from .env.  The .env shall be the source of all truth.
Create a .env.sample. Make sure to keep everything sensitive/custom outside of git 
and in .gitignore.

Make sure to include liveness and health check in the container.

Write documentation in docs/

Include documentation on how to build, test, and run the container locally.

When done, deploy the server on k8s. 
