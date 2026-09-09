# Marlowe. Sourced before node.sh on every node a job holds; declarations only.
#
# The home is shared NFS with a small quota, so the pixi cache and the clones
# live under the project's Lustre allocation and are linked from the home.
# The only node-local storage is the per-job directory slurm's prolog makes on
# the node's NVMe and its epilog deletes: that is TMPDIR and nothing else.
# /tmp is the root disk and is routinely full.

site_detect() { [[ -d /marlowe ]]; }
NODE_HOME=/users/$USER
SCRATCH=/scratch/m000137-pm06/$USER
# A batch script's PATH has no slurm and no slurm.conf; the script needs
# srun, scancel and scontrol.
SLURM_BIN=/cm/shared/apps/slurm/current/bin
export SLURM_CONF=/cm/shared/apps/slurm/var/etc/slurm/slurm.conf
# A requeue gets a fresh one, so nothing a resume needs goes here.
TMPROOT=/local_scratch/$USER.$SLURM_JOB_ID
IN_SCRATCH=(.cache roach_clones)
site_job_env() {
    # The site's `module load mps`: a per-job MPS pipe location, which CUDA
    # uses only if a control daemon is listening there.
    export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps-$SLURM_JOB_ID
    export CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-log-$SLURM_JOB_ID
}
