# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Entry point so ``python -m dotfiles_install`` runs the installer CLI."""

from dotfiles_install.cli import app

if __name__ == "__main__":
    app()
