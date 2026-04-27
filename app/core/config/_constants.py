import os

ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

if os.environ.get("ENV_FILE"):
    ENV_FILE = os.environ["ENV_FILE"]
elif os.path.isfile(os.path.join(os.getcwd(), ".env")):
    ENV_FILE = os.path.join(os.getcwd(), ".env")
else:
    ENV_FILE = os.path.join(ROOT_PATH, ".env")

logo = r"""

    _                    _
   / \   __ _  ___ _ __ | |_ ___
  / _ \ / _` |/ _ \ '_ \| __/ __|
 / ___ \ (_| |  __/ | | | |_\__ \
/_/   \_\__, |\___|_| |_|\__|___/
        |___/               Agents

"""
