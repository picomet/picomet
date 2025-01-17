Action
======

An ``action`` is a server function which is called from the client using the ``call`` function.

The ``call`` function makes a ``POST`` request with a payload to the server. The action function takes the ``HttpRequest`` object as an argument and can peform any operation, then should return a :ref:`Targets <targets>` list. Picomet uses that ``Targets`` list to partially render the specific target elements on the server. Then the partialls are sent as the response to be updated on the client.

Call
----

Provided by ``picomet/comet.js``

.. code-block:: typescript

  call(
    action: string,
    payload: {[key: string]: string | number | boolean | Blob} | FormData,
    keys?: [string, number][][]
  ): Promise<void>

.. list-table::
   :header-rows: 1

   * - Parameter
     - Description
   * - action: string
     - Action location ``app.actions.func`` > ``app.func``
   * - | payload: {
       |   [key: string]: string | number | boolean | Blob
       | } | FormData
     - | Payload sent to the action as post body
       |
       |
   * - keys?: [string, number][][]
     - Optional loop keys array for loop item partial rendering


Usage
-----

First of all, lets create a ``Blog`` and a ``Like`` model:

.. code-block:: python

  # apps/core/models.py
  from django.db import models

  class Blog(models.Model):
      title = models.CharField(max_length=150)
      content = models.TextField()
      created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

  class Like(models.Model):
      blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
      created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.blog.title

Migrate the models:

.. code-block:: shell

  python manage.py makemigrations
  python manage.py migrate

Now enter into the django shell and create a blog:

.. code-block:: shell

  python manage.py shell

.. code-block:: python

  from core.models import Blog

.. code-block:: python

  Blog.objects.create(title="First blog", content="This is the content")

Define a like action:

.. code-block:: python

  # apps/core/actions.py
  from core.models import Blog, Like

  def like_blog(request):
      blog = Blog.objects.get(id=request.POST["blog"])
      Like.objects.create(blog=blog)
      return ["&likes"]

Create a Template and ``call`` the action from the client:

.. code-block:: html

  <!-- apps/core/comets/Blogs.html -->
  <div s-for="blog" s-in="blogs" s-of="blogs.filter(id=key)" s-key="blog.id">
    <div s-keys>
      <h2>{$ blog.title $}</h2>
      <p>{$ blog.content $}</p>
      <span s-group="likes">likes ({$ blog.like_set.count() $})</span>
      <button
        x-on:click="call('core.like_blog', {blog: $X(`blog.id`)}, keys)"
        s-csrf
      >
        like
      </button>
    </div>
  </div>

Create the view:

.. code-block:: python

  # apps/core/views.py
  from picomet.decorators import template
  from picomet.views import render
  from core.models import Blog

  @template("Blogs")
  def blogs(request):
      context = {"blogs": Blog.objects.all()}
      return render(request, context)

Configure url:

.. code-block:: python
  :emphasize-lines: 9

  # apps/core/urls.py
  from django.urls import path

  from core import views

  app_name = "core"

  urlpatterns = [
      path("blogs", views.blogs, name="blogs"),
  ]


Redirect
--------

class ``picomet.shortcuts.ActionRedirect``

.. list-table::
   :header-rows: 1

   * - Parameter
     - Description
   * - redirect_to: str
     - Path to redirect
   * - update: bool = True
     - Whether to update the page after redirection

Return a redirection from an action

.. code-block:: python

  # apps/core/actions.py
  from picomet.shortcuts import ActionRedirect

  def my_action(request):
      if not request.POST.get("var"):
          raise ActionRedirect("/")
