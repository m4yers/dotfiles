# Home, Sweet Home

Installs my work osx work environment.

## Installers
Each util that has explicit configuration occupies a separate folder, e.g.
*vim*.  Every such folder contains a script called *install.sh* that will be
greped and sourced by the main installer. Each installer provides system
install routine and optionally a set of directives to install required software
using brew, cask, pip or npm.

Here is an example vim installer script:
```
#brew: curl, ag, macvim --with-override-system-vim
#pip:  pylint, bashate
#npm:  jsonlint, eslint
install() {
  ln -s -f $ROOT/vim/vimrc ~/.vimrc

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi
}
```

Before *install* function is run all its brew, pip and npm dependencies will
be fulfilled.

## Directives

*(in pgogress)*<br>
An install directive like brew or pip is a quick way to add a dependency to an
install script. Though it is not required to use them, it is preferred.
Specifying install dependencies allows to build a dependency graph and run
tools installers first before their usage.
