# ollie-integrations-google-adk

Native Google ADK integration for Ollie. Package path in the public monorepo: [](https://github.com/varunnaganathan/ollie-integrations/tree/main/google-adk).

## Install

Collecting ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0
  Cloning https://github.com/varunnaganathan/ollie-sdk.git (to revision v0.3.0) to /private/var/folders/08/p3h5xwsj2_17fdz4q35ltxq00000gn/T/pip-install-_e35kn7s/ollie-sdk_3563a70949f5449b846a5ff08ebd980a
  Resolved https://github.com/varunnaganathan/ollie-sdk.git to commit 66d5937479be839643cb072c1c6097b6c158f698
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'done'
  Preparing metadata (pyproject.toml): started
  Preparing metadata (pyproject.toml): finished with status 'done'
Requirement already satisfied: httpx>=0.24.0 in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (0.28.1)
Requirement already satisfied: anyio in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (4.9.0)
Requirement already satisfied: certifi in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (2025.1.31)
Requirement already satisfied: httpcore==1.* in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (1.0.7)
Requirement already satisfied: idna in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (3.4)
Requirement already satisfied: h11<0.15,>=0.13 in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from httpcore==1.*->httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (0.14.0)
Requirement already satisfied: sniffio>=1.1 in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from anyio->httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (1.3.0)
Requirement already satisfied: typing_extensions>=4.5 in /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages (from anyio->httpx>=0.24.0->ollie-sdk@ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0) (4.15.0)
Building wheels for collected packages: ollie-sdk
  Building wheel for ollie-sdk (pyproject.toml): started
  Building wheel for ollie-sdk (pyproject.toml): finished with status 'done'
  Created wheel for ollie-sdk: filename=ollie_sdk-0.3.0-py3-none-any.whl size=36389 sha256=2c4f62642fa3987c6263a55c920b78a28e2f085877b6c06c6228183f0ead4c55
  Stored in directory: /private/var/folders/08/p3h5xwsj2_17fdz4q35ltxq00000gn/T/pip-ephem-wheel-cache-8sbdfcqy/wheels/94/01/a3/511f4c2a57a11f84eade2283d582c7b6b6af82f70f4c3d79bb
Successfully built ollie-sdk
Installing collected packages: ollie-sdk
  Attempting uninstall: ollie-sdk
    Found existing installation: ollie-sdk 0.2.0
    Uninstalling ollie-sdk-0.2.0:
      Successfully uninstalled ollie-sdk-0.2.0
Successfully installed ollie-sdk-0.3.0
Collecting ollie-integrations-google-adk@ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.2#subdirectory=google-adk (from ollie-integrations-google-adk[agent]@ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.2#subdirectory=google-adk)
  Cloning https://github.com/varunnaganathan/ollie-integrations.git (to revision google-adk-v0.3.2) to /private/var/folders/08/p3h5xwsj2_17fdz4q35ltxq00000gn/T/pip-install-4_3q905b/ollie-integrations-google-adk_2992723e7c1f4b5caa247bd9bd4af7e0

## Quick start



See [docs/INSTRUMENTATION.md](docs/INSTRUMENTATION.md).
