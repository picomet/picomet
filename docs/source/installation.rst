Installation
============

**Requirements**

-   `Python <https://www.python.org/downloads>`_ 3.12 or later
-   `uv <https://docs.astral.sh/uv/getting-started/installation>`_ 0.5.0 or later

**1.**
Scaffold a new project

.. code-block:: shell

  uvx --with copier -p 3.12 picomet startproject my-project

Then choose from the given options to customize your project. You can also just press enter to go with the defaults.

**2.**
Enter into the project folder

.. code-block:: shell

  cd my-project

**3.**
Install the dev dependencies

.. code-block:: shell

  uv sync --group dev

If using **Tailwind**

.. code-block:: shell

  npm i

**4.**
Start the development server

.. code-block:: shell

  uv run manage.py runserver


Now go to http://localhost:8000 with your web browser to see it running.
