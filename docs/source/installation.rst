Installation
============

**1.**
Create your project folder and ``cd`` into it

.. code-block:: shell

  cd projectfolder

**2.**
Now create a virtual environment named ``env``

.. code-block:: shell

  python -m venv env

**3.**
Activate the virtual environment

  On Windows

  .. code-block:: shell

    env\Scripts\activate.bat

  On Linux/Mac

  .. code-block:: shell

    source env/bin/activate


**4.**
Install `picomet <https://pypi.org/project/picomet>`_ , `copier <https://pypi.org/project/copier>`_ and `django <https://pypi.org/project/django>`_

.. code-block:: shell

  pip install picomet copier django

**5.**
Generate the project

.. code-block:: shell

  picomet startproject

**6.**
Install the project requirements

.. code-block:: shell

  pip install -r requirements/dev.txt

If using **Tailwind**

.. code-block:: shell

  npm i

**7.**
Start the development server

.. code-block:: shell

  python manage.py runserver
