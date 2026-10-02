# AWS

An AWS ParallelCluster named `roach` in us-east-1 (account 851687812557,
the Amazon AI Fellowship's credits). Code: `roach.slurm.clusters.aws`
(`AWS`, `H100`, `H100_SPOT`, `A100`, `A100_SPOT`, `A10G`); the cluster itself is
`roach/slurm/clusters/aws/cluster.yaml`, driven by `pcluster.sh` next to it.
Monitor: [`scripts/aws-watch.sh`](../scripts/aws-watch.sh).

**Only on the human's instruction, and only the node count the human
gave.** The shape is `H100` (a p5.48xlarge) unless the instruction names
another: per dollar it does the most work. Every node-hour is dollars off a
finite pool of credits, which do not apply retroactively: usage past the
balance bills the human's card. There is no tier to fill and no free card
to find.

## Remote

The session never runs on AWS. `AWS.submit_host="aws"` makes `submit()` and
`Job.state` go over `ssh aws` (the alias in `~/.ssh/config`: the head node's
elastic IP, user `ubuntu`, key `~/scratch/.secrets/aws_ssh`; no gate, no
ControlMaster needed). `$A` below is `ssh -o BatchMode=yes aws`. The AWS
CLI here reads its credentials from `~/scratch/.secrets/aws` (an env file:
`set -a; . ~/scratch/.secrets/aws; set +a` before any `aws` or `pcluster`
command); there is no `~/.aws`.

## Nodes and storage

The head node is a `t3.medium`, permanent, ~$30/month plus the NAT gateway
and the FSx volume (~$200/month together). Compute nodes exist only while a
job holds them: slurm asks EC2 for one when a job is queued (2-5 minutes to
boot), and ParallelCluster terminates it 5 minutes after it goes idle.

| queue | instance | cards | vCPUs | memory | billing |
| --- | --- | --- | --- | --- | --- |
| `h100` | p5.48xlarge | 8 x H100-80G | 192 | 2 TB | on demand, ~$55/h |
| `h100-spot` | p5.48xlarge | same | | | spot, reclaimed with 120 s notice |
| `a100` | p4d.24xlarge | 8 x A100-40G | 96 | 1.1 TB | on demand, ~$33/h |
| `a100-spot` | p4d.24xlarge | same | | | spot |
| `h100-1{a..f}` | p5.4xlarge | 1 x H100-80G | 16 | 256 GB | on demand, ~$7.5/h; one queue per AZ |
| `h100-1{a..f}-spot` | p5.4xlarge | same | | | spot, a separate capacity pool; 120 s notice |
| `a10g` | g5.2xlarge | 1 x A10G-24G | 8 | 32 GB | on demand, ~$1.2/h; probes and debugging, 1 node |

Up to 4 nodes per queue (`MaxCount` in `cluster.yaml`; raise it and the EC2
quota together). All in one AZ (us-east-1d) with EFA and a placement group,
so multi-node jobs get the fast interconnect.

| path | what | use for |
| --- | --- | --- |
| `~` = `/fsx/home/ubuntu` | the roach home on FSx Lustre, shared by every node | pixi, `~/roach_clones` |
| `~/scratch` -> `/fsx/scratch/ubuntu` | the same FSx, 1.2 TB (`SCRATCH_2`, no backup) | logs, checkpoints, data, `.secrets` |
| `/scratch` | the instance's NVMe, formatted at boot | `TMPDIR`; gone with the instance |
| `/home/ubuntu` | the head node's disk, NFS-exported | nothing |

Measured on the first job (a g5.2xlarge, 2026-09-09): 3.5 min from
submit to the node accepting the job (`CONFIGURING` while EC2 boots it), then
`node.sh` installed pixi onto FSx in ~20 s, clone 1 s, `pixi install` 26 s
with the submitter's lock, and the rank started. Those are the expected gaps
in a log, not stalls. pixi warns that its repodata cache is on Lustre and
redirects it to the NVMe: harmless.

**FSx is scratch-class storage with no backup**: a `pcluster delete-cluster`
deletes it. Anything worth keeping is copied off (to S3, or here) before
the cluster is torn down.

## Read the cluster, every submission

```
$A squeue -o "%.8i %.30j %.12P %.9T %.10M %R"                 # yours, with reasons
$A sinfo -o "%P %D %t %E"                                       # what is up, and why a node is down
set -a; . ~/scratch/.secrets/aws; set +a
aws ce get-cost-and-usage --time-period Start=$(date +%Y-%m-01),End=$(date -d tomorrow +%Y-%m-%d) \
    --granularity MONTHLY --metrics UnblendedCost --query 'ResultsByTime[0].Total.UnblendedCost.Amount'   # this month's gross spend
aws service-quotas get-service-quota --service-code ec2 --quota-code L-417A185B --query Quota.Value        # P-instance vCPU quota (192 per p5/p4d node)
```

A pending job here is EC2 not handing over a node, not a queue: the reason
reads `Resources`/`Priority` while ParallelCluster launches, and stays there
if EC2 has no capacity (`InsufficientInstanceCapacity` in
`$A sudo tail /var/log/parallelcluster/clustermgtd`) or the quota is 0. p5 on
demand is often unavailable; `h100-spot`, `a100`, or a Capacity Block are
the alternatives, and the human picks. A spot node reclaimed mid-run shows as
a job back in PENDING with `Restarts>0`: it resumes from its checkpoint, if
it has one.

## Resource shapes

The presets are whole nodes (`gpus="8"`, `exclusive=True`, no account, no
qos: ParallelCluster runs no accounting). `nodes=N` up to 4. Smaller jobs
(`gpus="1"`) still pay for the whole instance, since a node is launched per
job and the queues are one instance type: there is no cheaper card to fall
back on, so pack work into whole nodes.

## Cluster lifecycle

```
roach/slurm/clusters/aws/pcluster.sh status | create | update | setup | delete
```

`update` applies `cluster.yaml` (queues drain first). `setup` runs once after
`create`: it makes the FSx homes, copies the secrets, and points the head
node's login at `/fsx` and `/opt/slurm/bin`, then prints the ssh alias to
put in `~/.ssh/config`. Quota increases (P-instance on-demand and spot vCPUs,
`L-417A185B` / `L-7212CCBC`) are filed in Service Quotas and take days.

## Quotas and the capacity shortage (2026-09-23)

us-east-1: P on-demand 64 vCPUs, P spot 64, G 8, Concurrent P5 Capacity
Blocks 1. A p5.48xlarge needs 192 vCPUs and a p4d 96, so 64 fits only four
p5.4xlarge (16 vCPUs each).

**p5.4xlarge has returned InsufficientInstanceCapacity in every us-east-1 AZ,
on demand and on spot, continuously since 2026-09-11.** No GPU node has
launched. A Capacity Block is reserved capacity and is the way around that,
but the fellowship credits cannot buy one yet: the program told Fellows on
2026-09-23 not to attempt it and promised a fix in "a few weeks". **Do not
buy a Capacity Block until that is confirmed** -- it bills real money, not
credits.

Two one-GPU probe jobs sit queued on `h100-1*` and `h100-1*-spot` as a free
capacity watcher: they cost nothing while pending and start the moment EC2
has a node.

## Torn down 2026-09-30

The cluster and the FSx volume are both deleted; the account now bills nothing.
The 1.2 TB volume (`fs-09245015f32279013`) held only a partial HF download
against a superseded dataset revision and stale checkpoint layouts, all
re-fetchable from the Hub. **A rebuild must start the `the-join-preprocessed`
download first, not last**: it is a few hundred GB and took days from the head
node.

What survives in the account, and what a rebuild needs:

| survives | id | note |
| --- | --- | --- |
| FSx security group | `sg-04d0f27eb6ae6f0ba` | allows Lustre 988 and 1018-1023 from the VPC; without it a re-attach is refused |
| private subnets, one per AZ | see `cluster.yaml` | free |
| private route table | `rtb-003bcc352a9bcae62` | free; its 0.0.0.0/0 route is now dangling |

A rebuild must recreate the FSx volume as well as the NAT gateway and its
elastic IP, then point `SharedStorage` in `cluster.yaml` at the new
`FileSystemId`:

```bash
set -a; . ~/scratch/.secrets/aws; set +a
export AWS_DEFAULT_REGION=us-east-1
aws fsx create-file-system --file-system-type LUSTRE --storage-capacity 1200 \
      --subnet-ids subnet-010977c26143e3853 --security-group-ids sg-04d0f27eb6ae6f0ba \
      --lustre-configuration DeploymentType=SCRATCH_2 \
      --query FileSystem.FileSystemId --output text   # put this in cluster.yaml
EIP=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
NAT=$(aws ec2 create-nat-gateway --subnet-id subnet-010977c26143e3853 --allocation-id $EIP \
      --query NatGateway.NatGatewayId --output text)
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT
aws ec2 replace-route --route-table-id rtb-003bcc352a9bcae62 \
      --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT
roach/slurm/clusters/aws/pcluster.sh create   # ~20 min
roach/slurm/clusters/aws/pcluster.sh setup    # prints the new ssh alias
```

The head node gets a new elastic IP, so update the `aws` entry in
`~/.ssh/config` (both the AFS and the node-local copy) with the address
`setup` prints.

## Cardinal Cloud move: timing trap (2026-10-01)

Ticket RITM00794840 was filed 2026-09-30 and Stanford sent the Organization
invitation the same afternoon (handshake `h-9c301391d4f149b09027b44433c0064a`,
org `o-8iwvd2taf5`, "SU AWS Main", expires **2026-10-15**).

**Do not accept it before the last day of a month.** Dominic Young (AWS), in
writing on 2026-09-15: "When an account moves mid-month the credits cease to
apply for the remainder of that month and will start up again the first of the
month, so we recommend moving the account on the last day of the month."
Accepting on 1 October would forfeit credit coverage for all of October,
including the mid-October Capacity Block.

The invitation expires before 31 October, so it has to be re-issued. Bruno
Velazquez agreed on 2026-10-01: **he will re-send the invitation on 30 October
and the ticket stays open until the move is done; accept it on 31 October.**
The 2026-10-15 handshake is being left to lapse on purpose.

## Why the quota fight stopped mattering

"Instances in a Capacity Block don't count against your On-Demand Instances
limits" (EC2 user guide). The Concurrent P5 Capacity Blocks quota is already
192 vCPUs, i.e. one whole p5.48xlarge, so the 64-vCPU on-demand and spot P
quotas are irrelevant on this path. The Organization move is now insurance and
long-term support, not the unblocker.

Blocked only on Amazon enabling fellowship credits for Capacity Blocks; Ellen
Hermansen, 2026-09-24, "within the next few weeks", no date. Until then a
purchase bills a personal credit card, so never buy one unprompted.

Live supply is thin. `aws ec2 describe-capacity-block-offerings --instance-type
p5.48xlarge --instance-count 1 --capacity-duration-hours 48` returned exactly
one offering on both 09-30 and 10-01: us-east-1f starting 2026-10-17, $1993.34
upfront ($41.53/h for all eight H100s). A 262-GPU-hour pretrain is ~33 h wall
clock, so a 48 h block covers it.

The dataset download is the critical path, not the cluster: a few hundred GB
that took days from the head node. Rebuild and start the fetch ~4 days before
the block begins, at ~$7/day.

