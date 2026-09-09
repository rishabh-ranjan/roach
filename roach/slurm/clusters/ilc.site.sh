# ILC. Sourced before node.sh on every node a job holds; declarations only.
#
# Per-node NVMe at /lfs/local/0 holds the home, pixi, the clones and TMPDIR;
# /dfs/user/$USER is the shared filesystem, the same path on every node.

site_detect() { [[ -d /lfs/local/0 && -d /dfs/user ]]; }
NODE_HOME=/lfs/local/0/$USER
SCRATCH=/dfs/user/$USER
SLURM_BIN=
SLURM_CONF=
# /tmp is the root filesystem, a few hundred GB shared with the OS: a job whose
# scratch fills it wedges every job on the node. The NVMe is for exactly this,
# and a resume point kept there survives a requeue.
TMPROOT=/lfs/local/0/$USER/tmp
IN_SCRATCH=()
site_job_env() { :; }
