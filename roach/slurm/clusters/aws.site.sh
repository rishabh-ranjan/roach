# AWS (ParallelCluster). Sourced before node.sh on every node a job holds;
# declarations only.
#
# Nothing on a compute node outlives it: the fleet scales to zero. The home
# and the shared store are both on the cluster's FSx for Lustre, mounted at
# /fsx on every node, so a node that just booted finds the pixi it needs
# there. ParallelCluster mounts an instance's NVMe at /scratch; that is
# TMPDIR, and it is gone with the instance.

site_detect() { [[ -d /opt/parallelcluster ]]; }
NODE_HOME=/fsx/home/$USER
SCRATCH=/fsx/scratch/$USER
SLURM_BIN=/opt/slurm/bin
SLURM_CONF=
TMPROOT=/scratch/$USER
IN_SCRATCH=()
site_job_env() { :; }
