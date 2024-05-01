View
====

Setup
-----

First of all, create a comet template:

.. code-block:: text

  <!-- apps/core/comets/pages/New.html -->
  <div>
    {$ variable $}
  </div>

Learn more about :doc:`/comet` template.

Define a view:

.. code-block:: python

  # apps/core/views.py
  from picomet.decorators import template
  from picomet.views import render

  @template("pages/New")
  def new(request):
      context = {"variable": "hello world"}
      return render(request, context)


Configure url:

.. code-block:: python

  # apps/core/urls.py
  from django.urls import path

  from core import views

  app_name = "core"

  urlpatterns = [
      path("new", views.new, name="new"),
  ]


Redirect
--------

class ``picomet.http.PicometResponseRedirect``

.. list-table::
   :header-rows: 1

   * - Parameter
     - Description
   * - redirect_to: str
     - Path to redirect
   * - update: bool = True
     - Whether to update the page after redirection
   * - headers: dict = None
     - Http headers to be sent with the response


.. code-block:: python

  # apps/core/views.py
  from django.contrib.auth.forms import UserCreationForm
  from picomet.http import PicometResponseRedirect

  @template("Index")
  def index(request):
      if request.method == "POST" and not request.action:
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return PicometResponseRedirect("/acount")

.. note::
  ``PicometResponseRedirect`` can only be returned when ``request.targets`` has any targets or ``request.action`` exists.
