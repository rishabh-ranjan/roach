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

## philosophy

I have converged to a particular experiment management workflow
after a few years of empirical research in acadmemic settings.
This README describes the complete workflow.
`roach` provides the supporting code.
I refer the whole framework (workflow + code in this repo) as `roach`.

`roach` is fluid and evolving,
although the core tenets have been stable for a while now,
and battle-tested over a bunch of large-scale empirical research projects.
While others may use `roach` or draw inspiration from it,
I do not care for backwards compatibility
or general-purpose usability.
Part of the attraction of having a custom framework
is the freedom to implement idiosyncratic features
for bespoke use-cases without constraints.
I am especially wary of feature bloat
and over-engineering,
and aim to keep `roach` lean and focused.

## overview

### roach tasks, queues, and workers

A 


`roach` actually consists of some independent parts:
* Utilities to generate publication-quality plots and tables for paper-writing.
* Storing and retrieving metadata, curves and artifacts across many experimental runs.
* A queing system with submit and worker functionalities.

`roach.paper` has plot- and table-generation utilities for
writing papers.

`roach.store` provides a simple abstraction to store
metadata, learning curves, and other artifacts,
with minimal cognitive load,
allowing for controlled retrieval and analysis over many experimental runs.

`roach.submit` allows submitting tasks to queues,
along with dependencies.

`roach.worker` provides workers.

## install

```bash
pip install git+https://github.com/rishabh-ranjan/roach
```


