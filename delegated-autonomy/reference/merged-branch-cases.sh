#!/usr/bin/env bash
# Reproduces the merged-branch detection matrix in merged-branch-check.md.
# Run in an empty scratch directory: bash merged-branch-cases.sh
# It prints the table rows, uses only ./r in the current directory, removes
# it when done, and refuses to start if ./r already exists.
set -e
[ ! -e r ] || { echo "./r exists; run this in an empty directory" >&2; exit 1; }
g(){ git -c user.name=t -c user.email=t@t "$@" >/dev/null 2>&1; }
setup(){ rm -rf r && git init -q -b main r && cd r && printf 'a\nb\nc\n' > f && echo x > other && g add . && g commit -m base; }
feat(){ g checkout -q -b $1; printf 'a\nB1\nc\n' > f; g commit -am f1; echo n >> new; g add new; g commit -m f2; g checkout -q main; }
check(){ b=$1; anc=no; git merge-base --is-ancestor $b main && anc=yes
  ch=$(git cherry main $b | grep -c '^+' || true)
  mt=$( [ "$(git merge-tree --write-tree main $b 2>/dev/null | head -1)" = "$(git rev-parse main^{tree})" ] && echo yes || echo no )
  printf '| %s | %s | %s | %s |\n' "$2" $anc $ch $mt; }
( setup; feat t; g merge --no-ff t -m m; check t "Merge commit" )
( setup; feat t; g merge --ff-only t; check t "Fast-forward" )
( setup; feat t; echo y>other; g commit -am m2; g checkout -q t; g rebase -q main; g checkout -q main; g merge --ff-only t; check t "Branch rebased, then fast-forward" )
( setup; feat t; echo y>other; g commit -am m2; g cherry-pick $(git rev-list --reverse main..t); check t "Rebase merge, clean (new commits)" )
( setup; feat t; printf 'a\nM\nc\n' > f; g commit -am mainchange; for c in $(git rev-list --reverse main..t); do g cherry-pick $c || { printf 'a\nB1+M\nc\n' > f; g add f; g -c core.editor=true cherry-pick --continue; }; done; check t "Rebase merge with a conflict" )
( setup; feat t; g merge --squash t; g commit -m sq; check t "Squash merge, clean" )
( setup; feat t; printf 'a\nM\nc\n' > f; g commit -am mainchange; g merge --squash t || true; printf 'a\nB1+M\nc\n' > f; g add f; g commit -m sq-conflict; check t "Squash merge with a conflict" )
( setup; feat t; g merge --squash t; g commit -m sq; printf 'a\nLATER\nc\n' > f; g commit -am later; check t "Squash merge, then main changes the same lines" )
( setup; feat t; g merge --squash t; g commit -m sq; g checkout -q t; echo extra>>new; g commit -am extra; g checkout -q main; check t "Squash merge, then a new commit on the branch" )
( setup; feat t; g merge --no-ff t -m m; g checkout -q t; echo z>>new; g commit -am post; g checkout -q main; check t "Merged, then a new commit on the branch" )
( setup; feat t; g merge --no-ff t -m m; g revert -m 1 --no-edit HEAD; check t "Merged, then reverted on main" )
( setup; feat t; check t "Never merged" )
( setup; feat t; printf 'a\nB1\nc\n' > f; g commit -am "same edit made on main"; check t "Never merged, main made the same edit" )
rm -rf r
