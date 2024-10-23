# Contributing to Picomet

Welcome to Picomet! We're excited to have you contribute. Before you get started, please take a moment to review this guide to understand how to contribute effectively.

## Prerequisites

Before you begin contributing to Picomet, make sure you have the following installed

-   [Python 3.12](https://www.python.org/downloads) or later
-   [Node 20.11](https://nodejs.org) or later

## Setting up the project

1. [Fork the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo#forking-a-repository)

1. [Clone the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo#cloning-your-forked-repository)

1. Navigate to the project folder

    ```bash
    cd picomet
    ```

1. Create a virtual environment

    ```bash
    python -m venv env
    ```

1. Activate the virtual environment

    On Windows

    ```bash
    env\Scripts\activate.bat
    ```

    On Linux/Mac

    ```bash
    source env/bin/activate
    ```

1. Install required packages

    ```bash
    pip install -r requirements.txt
    pip install -e .
    ```

    ```bash
    npm install
    ```

1. Install pre-commit

    ```bash
    pre-commit install-hooks
    ```

    ```bash
    pre-commit install
    ```

## Development workflow

1. Create a branch

    ```bash
    git checkout -b feature/my-feature
    ```

1. Write code

    Write your code, following the project's coding standards and guidelines.

1. Commit changes

    Use meaningful commit messages. If your change fixes a specific issue, reference it in the commit message

    ```bash
    git commit -m "Your commit message"
    ```

1. Push changes

    Push your changes to your forked repository

    ```bash
    git push origin feature/my-feature
    ```

1. [Open a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)

    Once your changes are ready, open a pull request on the main repository. Provide a clear description of your changes and reference any related issues.

1. Review and iterate

    Collaborate with maintainers and other contributors to address any feedback on your pull request. Make necessary changes and push them to the same branch.

1. Merge pull request

    Once your pull request is approved, it will be merged into the main branch. Congratulations on your contribution!

Thank you for contributing to Picomet! 🎉 We appreciate your help in making this project better.
