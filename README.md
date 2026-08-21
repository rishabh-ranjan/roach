# roach -- fearless experiment management

Per [wikipedia](https://en.wikipedia.org/wiki/Cockroach#Hardiness), roaches:
> * are capable of remaining active for a month without food
> * are able to survive on limited resources
> * can go without air for 45 minutes
> * have survived twelve hours at −5 to −8 °C (23 to 18 °F)
> * are also able to survive decapitation
> * will "inherit the Earth" if humanity destroys itself in a nuclear war

Same goes for `roach` experiments.

`roach` is an experiment management framework, intended primarily for use by
close collaborators and me.

## install

As a dependency, pinned to a tag:

```toml
# pyproject.toml
dependencies = ["roach @ git+https://github.com/rishabh-ranjan/roach@v0.1.0"]
```

For development:

```bash
git clone https://github.com/rishabh-ranjan/roach
cd roach
pixi install
pixi run test
```

## roach slurm

Run a python function on slurm -- one job, one rank per GPU, resumable across
preemption and the wall clock. **[roach/slurm/README.md](roach/slurm/README.md)**.

## roach paper

`roach.paper`: matplotlib/seaborn defaults and save helpers for paper figures
and tables.
