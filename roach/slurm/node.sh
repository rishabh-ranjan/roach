# What a batch job's environment looks like, on any cluster. Spliced into the
# batch script right after the cluster's site file and run on every node the
# job holds, before the clone is touched.
#
# The site file is declarations only: where the home is, where the shared
# store is, where slurm lives, where a job's scratch goes. Everything here is
# the same on every cluster: bring the home to spec (a pinned pixi, the links
# into the shared store), put the tokens in the environment, set TMPDIR.
#
# Roach assumes nothing about the home beyond what this file creates. A
# dotfiles checkout, global tools, a shell: the user's business, done by the
# user's own login, never read here.
#
# No fallbacks: anything that cannot be reinstated is a hard error here,
# seconds into the job, rather than a silently degraded run discovered hours
# later. Idempotent, and serialized: several jobs land on a fresh node at once,
# the first sets it up and the rest wait and find it done.

set -euo pipefail

die() { echo "node: $*" >&2; exit 1; }

export USER=${USER:-$(id -un)}
site_detect || die "$(hostname -s) is not a node of this cluster"

export HOME=$NODE_HOME
mkdir -p "$HOME" || die "cannot create $HOME on $(hostname -s)"
exec 8>"$HOME/.roach-node.lock"
flock 8 || die "cannot lock $HOME/.roach-node.lock"

# $HOME/<name> -> <target>, and nothing else may be there. A real directory
# is a node that wrote to local disk by mistake -- slurm makes one when it
# opens a job's log under ~/scratch before this has run on the node -- and it
# is never deleted here: look at what it holds, then replace it by hand.
link() {
    if [[ ! -L $HOME/$1 ]]; then
        [[ -e $HOME/$1 ]] && die "$HOME/$1 is a real directory on $(hostname -s), not a symlink;" \
            "inspect it, then: rm -rf $HOME/$1 && ln -s $2 $HOME/$1"
        ln -s "$2" "$HOME/$1"
    fi
    [[ -d $HOME/$1/ ]] || die "$HOME/$1 -> $2 is not a directory on $(hostname -s)"
}
# ~/scratch is the shared filesystem at the same path on every node, so a job
# submitted with ~/scratch paths reads and writes the same files wherever it
# lands.
link scratch "$SCRATCH"
for _name in "${IN_SCRATCH[@]}"; do
    mkdir -p "$SCRATCH/$_name"
    link "$_name" "scratch/$_name"
done

# One pixi everywhere: a manifest one version solves and another rejects is a
# job that fails on one cluster only.
PIXI_VERSION=0.71.3
export PIXI_HOME=$HOME/.pixi
if [[ ! -x $PIXI_HOME/bin/pixi ]]; then
    echo "node: installing pixi $PIXI_VERSION into $PIXI_HOME"
    curl -fsSL https://pixi.sh/install.sh | PIXI_HOME=$PIXI_HOME PIXI_VERSION=v$PIXI_VERSION bash >/dev/null
    [[ -x $PIXI_HOME/bin/pixi ]] || die "pixi install did not produce $PIXI_HOME/bin/pixi"
fi
export PATH=${SLURM_BIN:+$SLURM_BIN:}$PIXI_HOME/bin:/usr/local/bin:/usr/bin:/bin
if [[ $(pixi --version) != "pixi $PIXI_VERSION" ]]; then
    echo "node: pixi $(pixi --version | cut -d' ' -f2) -> $PIXI_VERSION"
    pixi self-update --version "$PIXI_VERSION" >/dev/null
fi
[[ -n $SLURM_CONF ]] && export SLURM_CONF
unset PYTHONPATH  # points into a home that is not this job's home
# pixi's package cache on the same filesystem as the clones, so environments
# reflink from it.
export XDG_CACHE_HOME=$HOME/.cache
mkdir -p "$XDG_CACHE_HOME"

export TMPDIR=$TMPROOT/tmp
mkdir -p "$TMPDIR" || die "no scratch at $TMPROOT on $(hostname -s)"

exec 8>&-

# Tokens come from the secrets dir rather than the job env, where slurm would
# record them. github is roach's own (the clone); the rest are exported for
# the run if present.
_secrets=@SECRETS_DIR@
_read_secret() {
    local v
    v=$(tr -d '[:space:]' < "$_secrets/$1")
    [[ -n $v ]] || die "empty secret $_secrets/$1"
    printf '%s' "$v"
}
[[ -r $_secrets/github ]] || die "missing secret $_secrets/github"
GITHUB_TOKEN=$(_read_secret github); export GITHUB_TOKEN GH_TOKEN=$GITHUB_TOKEN
if [[ -r $_secrets/wandb ]]; then WANDB_API_KEY=$(_read_secret wandb); export WANDB_API_KEY; fi
if [[ -r $_secrets/huggingface ]]; then
    HF_TOKEN=$(_read_secret huggingface); export HF_TOKEN HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
fi

# No OMP_NUM_THREADS: with task/cgroup slurm binds each task to its own
# cpus_per_task and OpenMP sizes its pool from that mask. A number here could
# only disagree with the allocation.

site_job_env

echo "node: host=$(hostname -s) HOME=$HOME pixi=$(pixi --version) TMPDIR=$TMPDIR"
