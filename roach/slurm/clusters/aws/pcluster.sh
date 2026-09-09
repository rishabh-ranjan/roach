#!/bin/bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
secrets=~/scratch/.secrets
set -a; . "$secrets/aws"; set +a
cfg="$here/cluster.yaml"
case ${1:-} in
    create)  pcluster create-cluster --cluster-name roach --cluster-configuration "$cfg" --rollback-on-failure false ;;
    update)  pcluster update-cluster --cluster-name roach --cluster-configuration "$cfg" ;;
    delete)  pcluster delete-cluster --cluster-name roach ;;
    status)  pcluster describe-cluster --cluster-name roach --query '{status:clusterStatus,ip:headNode.publicIpAddress}' ;;
    ip)      pcluster describe-cluster --cluster-name roach --query headNode.publicIpAddress | tr -d '"' ;;
    setup)
        # Once per cluster, after create: the head node's login puts slurm on
        # PATH and its HOME on /fsx for non-interactive ssh (which is how
        # roach reaches it), and the secrets go where every node reads them.
        ip=$("$0" ip)
        ssh -i "$secrets/aws_ssh" -o StrictHostKeyChecking=accept-new "ubuntu@$ip" bash -s <<'REMOTE'
set -euo pipefail
sudo mkdir -p /fsx/home /fsx/scratch && sudo chown ubuntu:ubuntu /fsx/home /fsx/scratch
mkdir -p /fsx/home/ubuntu /fsx/scratch/ubuntu/.secrets && chmod 700 /fsx/scratch/ubuntu/.secrets
[[ -L /fsx/home/ubuntu/scratch ]] || ln -s /fsx/scratch/ubuntu /fsx/home/ubuntu/scratch
grep -q roach-head /home/ubuntu/.bashrc || { printf '# roach-head\nexport HOME=/fsx/home/ubuntu\nexport PATH=/opt/slurm/bin:$HOME/.pixi/bin:$PATH\ncd "$HOME"\n' | cat - /home/ubuntu/.bashrc > /home/ubuntu/.bashrc.new && mv /home/ubuntu/.bashrc.new /home/ubuntu/.bashrc; }
REMOTE
        for s in github wandb huggingface; do
            [[ -r $secrets/$s ]] && scp -q -i "$secrets/aws_ssh" "$secrets/$s" "ubuntu@$ip:/fsx/scratch/ubuntu/.secrets/$s"
        done
        echo "head node $ip is set up; ssh alias: Host aws / HostName $ip / User ubuntu / IdentityFile $secrets/aws_ssh"
        ;;
    *) echo "usage: $0 create|update|delete|status|ip|setup" >&2; exit 2 ;;
esac
