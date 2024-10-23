# Example

A simple example project for testing and demonstrating Picomet.

## Requirements

-   Python 3.12 or higher
-   Node 18 or higher

## Setup

```sh
git clone https://github.com/picomet/picomet.git
cd picomet/example
npm install
python -m pip install -e ../
python -m pip install -r requirements/dev.txt
```

## Running

```sh
python manage.py migrate
python manage.py runserver
```

Open http://localhost:8000 in your browser.
