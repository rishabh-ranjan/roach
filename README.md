# roach -- fearless experiment management

Per [wikipedia](https://en.wikipedia.org/wiki/Cockroach#Hardiness), roaches:
> * are capable of remaining active for a month without food  
> * are able to survive on limited resources  
> * can go without air for 45 minutes  
> * have survived twelve hours at −5 to −8 °C (23 to 18 °F)  
> * are also able to survive decapitation  
> * will "inherit the Earth" if humanity destroys itself in a nuclear war  

Same goes for `roach` experiments.


`roach` is an experiment management framework,
intended primarily for use by close collaborators and me.

## install

```bash
uv pip install git+https://github.com/rishabh-ranjan/roach
```

```bash
git clone https://github.com/rishabh-ranjan/roach
cd roach
uv pip install -e .
```

## overview

`roach` houses 3 independent frameworks:

1. roach queues (`roach.submit` and `roach.worker` modules):
painless task queing and execution across heterogeneous resources and workloads

2. roach stores (`roach.store` module):
reliable tracking and analysis of experiment artifacts

3. roach paper utils (`roach.paper` module):
pretty plots and tables for research papers


## roach queues

### concepts

_Roach tasks_ are arbitrary shell commands, possibly multi-line.
_Roach task files_ are plaintext files containing
the task command,
a precondition check command (optional),
and outputs (stderr, stdout) of task command execution.

_Roach queues_ are directories,
e.g. `/dfs/user/ranjanr/roach/queues/<queue_name>`.
Keeping queues on `/dfs` means that
tasks sync across all machines on the SNAP cluster.
Task files have a _roach state_,
which can be one of:
- `queued`: task is waiting to be picked up by a worker,
- `checking`: the precondition check command is being run by a worker,
- `active`: the task command is being run by a worker,
- `done`: the task command completed successfully,
- `failed`: the task command failed, or,
- `paused`: the task is paused by the user.
Task files are grouped into _roach state directories_
within the queue directory.

_Roach workers_ can change task states.
You can also change task states manually
by moving task files between state directories.
Common use cases include:
- deleting a task file from `active` will kill it (by sending SIGKILL)
- moving a task file from `active` to `paused` will pause it (by sending SIGSTOP),
and moving it back to `active` will resume it (by sending SIGCONT).
- moving a task file from `failed` to `queued` will retry it

Workers add info to task files,
for ease of associating tasks with workers.


### submit

The recommended usage pattern is to use python:
```python
from roach.submit import submit

queue = "/dfs/user/ranjanr/roach/queues/example"
for seed in range(5):
    for lr in [1e-3, 1e-4]:
        cmd = rf"""python train.py
--seed={seed} \
--lr={lr} \
--save_ckpt='seed={seed}_lr={lr}.pt'
"""
        chk = submit(queue, cmd)

        cmd = rf"python eval.py --ckpt='seed={seed}_lr={lr}.pt'"
        # chk ensures that "eval" tasks wait for "train" tasks to get done
        submit(queue, cmd, chk=chk)
```

`chk` can be an arbitrary shell command,
so the check condition is really that this command exits with error code 0.
For example, to check that there's enough memory on the GPU and a checkpoint exists:
```python
chk_mem = "python -c 'import sys, torch; sys.exit(not torch.cuda.mem_get_info()[0] > 8e9)'"
chk_ckpt = "test -f 'seed={seed}_lr={lr}.pt'"
chk = f"{chk_mem} && {chk_ckpt}"
submit(queue, cmd, chk=chk)
```

You can also use the CLI:
```bash
python -m roach.submit /dfs/user/ranjanr/roach/queues/example 'echo hello world'
```


### worker

The basic CLI is:
```bash
python -m roach.worker /dfs/user/ranjanr/roach/queues/example &
```

The `&` runs the worker in the background,
which is the intended usage pattern.
As its common to run many workers together,
workers don't print much.
Worker state can be monitored by inspecting task files in
`active` and `checking`.
They can be killed with SIGTERM or by exiting the current shell.
Any running tasks will be moved back to `queued`.

The task runs in the same environment as the worker,
including current directory, conda/pixi environment, any environment variables, etc.
So, common usage looks like:
```bash
cd <project-dir>
pixi shell
# inside the pixi shell
for i in {0..7}
do
    CUDA_VISIBLE_DEVICES=$i python -m roach.worker /dfs/user/ranjanr/roach/queues/example &
done
```
