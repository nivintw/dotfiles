<!-- Shared content fragment, included via pymdownx.snippets (`--8<-- "install.md"`) from
     any docs page that needs install instructions, so they can't drift between copies
     (nivintw/repo-management#96). This starter file is a mechanism placeholder — real
     content is authored per repo by the generate-docs skill, not here.

     No inline SPDX header when markdown is frontmatter-first: markdown is then licensed via
     REUSE.toml's `**/*.md` annotation (see .config/licenserc.toml), and a line-1 header here
     would both defeat that convention and — since this fragment is spliced INTO other pages —
     inject the comment wherever it's included. When markdown is not frontmatter-first, hawkeye
     headers markdown inline, so the header above is present to satisfy that. -->

There is no toolchain to install first — `install.sh` bootstraps Homebrew and uv itself,
then hands off to the installer.

```bash
git clone https://github.com/nivintw/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

That one command converges a fresh machine to the declared setup: CLI tools, fish (zsh is a
selectable opt-in — `install.sh --shell zsh`), and — on macOS — GUI apps, the MesloLGS NF
font, the macOS defaults, and the Dock. On Linux and WSL2 the same OS-agnostic core runs and
the macOS-only phases skip themselves. It is safe to re-run: it *converges* the machine to the
declared state rather than clobbering what is already there.
