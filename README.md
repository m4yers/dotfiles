# Home, Sweet Home

Installs my osx work environment.

## Installers
Each util that has explicit configuration occupies a separate folder, e.g.
*vim*.  Every such folder contains a script called *install.sh* that will be
greped and sourced by the main installer. Each installer provides system
install routine and optionally a set of directives to request a dependency
or to provide one.

Here is an example vim installer script:
```
# depends-on: bash, brew, npm, svn
install() {
  brew install macvim
  brew install macvim --with-override-system-vim
  brew link --overwrite macvim
  brew install ag
  brew install swiftlint
  pip install pylint
  pip install bashate
  npm install -g jsonlint
  npm install -g eslint

  ln -s -f $THIS/vimrc ~/.vimrc
  ln -s -f $THIS/cvimrc ~/.cvimrc
  ln -s -f $THIS/vimrc ~/.ideavimrc
  ln -s -f $THIS/ycm.py ~/.ycm.py

  svn co http://llvm.org/svn/llvm-project/llvm/trunk/utils/vim $DEPENDENCIES/llvm.vim

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi

  bash_init_section
  bash_export_source "$THIS/bashrc.aliases.sh"
}
```

Before *install* function is run all its bash, brew, npm and svn dependencies will
be fulfilled.

## Directives

There are two directives:
 - \# depends-on: \<list-of-names\> Requests a dependency list to be fulfilled
   before this installer is run.
 - \# satisfies: <list-of-names> Provides dependencies for others to use.
   Essentially an export.

Before any installer is run a build order is defined so that each successive
installer is run after its dependencies are satisfied.

