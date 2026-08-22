# Marlowe: what a batch job's environment looks like. Sourced, on every node a
# job holds, before the clone is touched.
#
# The home is the shared /users checkout of the dotfiles (setup-node.sh), the
# same on every node, so nothing is set up per node here: the job only checks
# that the home is to spec and fails loudly if not. Persistent state lives
# under ~/scratch (Lustre, the project allocation): ~/.cache, ~/roach_clones
# and the secrets are symlinks or directories there. The only node-local
# storage is the per-job directory slurm's prolog makes on the node's NVMe
# and its epilog deletes; that is TMPDIR and nothing else. /tmp is the root
# disk and is routinely full: never write there.
#
# No fallbacks: anything that cannot be reinstated is a hard error here, seconds
# into the job, rather than a silently degraded run discovered hours later.

set -euo pipefail

die() { echo "slurm-env: $*" >&2; exit 1; }

export USER=${USER:-$(id -un)}
export HOME=/users/$USER
SETUP_URL=https://raw.githubusercontent.com/rishabh-ranjan/dotfiles/main/setup-node.sh

[[ -d $HOME/.git && -x $HOME/.pixi/bin/pixi ]] ||
    die "$HOME is not a dotfiles checkout with pixi; see $SETUP_URL"
for link in scratch .cache roach_clones; do
    [[ -L $HOME/$link && -d $HOME/$link/ ]] || die "$HOME/$link is not a symlink into scratch; run setup-node.sh"
done

# A batch script's PATH has no slurm and no slurm.conf; the script needs
# srun, scancel and scontrol.
export PATH=/cm/shared/apps/slurm/current/bin:$HOME/.pixi/bin:/usr/local/bin:/usr/bin:/bin
export SLURM_CONF=/cm/shared/apps/slurm/var/etc/slurm/slurm.conf
unset PYTHONPATH

# Shared state that no amount of node setup can create.
_secrets=$HOME/scratch/.secrets
for s in wandb huggingface github; do
    [[ -r $_secrets/$s ]] || die "missing secret $_secrets/$s"
done

export PIXI_HOME=$HOME/.pixi
export XDG_CACHE_HOME=$HOME/.cache  # -> ~/scratch/.cache: pixi's package cache on the
                                    # same Lustre as the clones, so environments hardlink

# Per-job node-local scratch: /local_scratch/$USER.$SLURM_JOB_ID, made by the
# prolog and removed by the epilog. A requeue gets a fresh one, so nothing a
# resume needs goes here.
_local=/local_scratch/$USER.$SLURM_JOB_ID
[[ -d $_local && -w $_local ]] || die "no per-job node-local dir $_local on $(hostname -s)"
export TMPDIR=$_local/tmp
mkdir -p "$TMPDIR"

# The site's `module load mps`: a per-job MPS pipe location, which CUDA uses
# only if a control daemon is listening there.
export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps-$SLURM_JOB_ID
export CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-log-$SLURM_JOB_ID

# Tokens come from the shared secrets dir rather than the job env, where slurm
# would record them; they were checked for readability above.
_read_secret() {
    local v
    v=$(tr -d '[:space:]' < "$_secrets/$1")
    [[ -n $v ]] || die "empty secret $_secrets/$1"
    printf '%s' "$v"
}
WANDB_API_KEY=$(_read_secret wandb); export WANDB_API_KEY
HF_TOKEN=$(_read_secret huggingface); export HF_TOKEN
export HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
GITHUB_TOKEN=$(_read_secret github); export GITHUB_TOKEN GH_TOKEN=$GITHUB_TOKEN

# TaskPlugin is task/cgroup, so nproc inside a task is its cpus_per_task
# (measured: 14 in a -c 14 task) and OpenMP sizes itself from that.

echo "slurm-env: host=$(hostname -s) HOME=$HOME pixi=$(pixi --version) TMPDIR=$TMPDIR"
