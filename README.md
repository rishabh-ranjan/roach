# roach -- fearless experiment management

Per [wikipedia](https://en.wikipedia.org/wiki/Cockroach#Hardiness), roaches:
> * are capable of remaining active for a month without food  
> * are able to survive on limited resources  
> * can go without air for 45 minutes  
> * have survived twelve hours at −5 to −8 °C (23 to 18 °F)  
> * are also able to survive decapitation  
> * will "inherit the Earth" if humanity destroys itself in a nuclear war  

Same goes for my experiments.


`roach` is an experiment management framework,
intended primarily for use by me, and close collaborators.

## install

```bash
uv pip install git+https://github.com/rishabh-ranjan/roach
```

```bash
git clone https://github.com/rishabh-ranjan/roach
cd roach
uv pip install -e .
```

## submit

```python
from roach.submit import submit

queue = "~/scratch/roach/queues/example"
cmd = rf"""
echo {queue}
echo hello world
"""
chk = submit(queue, cmd)

cmd = "echo world"
submit(queue, cmd, chk=chk)

chk = "python -c 'import sys, torch; sys.exit(not torch.cuda.is_available())'"
cmd = "python -c 'import torch; print(torch.cuda.get_device_name())'"
submit(queue, cmd, chk=chk)
```

```bash
python -m roach.submit ~/scratch/roach/queues/example 'echo hello world'
```

## worker

```bash
python -m roach.worker ~/scratch/roach/queues/example &
CUDA_VISIBLE_DEVICES='' python -m roach.worker ~/scratch/roach/queues/example &
```
