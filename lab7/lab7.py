from collections import defaultdict

W,H=4,3
WALL=(1,1)
TERMINALS={(3,2):1,(3,1):-1}
ACTIONS=[('U',(0,1)),('D',(0,-1)),('L',(-1,0)),('R',(1,0))]
STATES=[(x,y) for y in range(H) for x in range(W) if (x,y)!=WALL]

def step(s,d):
    n=(s[0]+d[0],s[1]+d[1])
    return n if n in STATES else s

def transitions(s,a,slip):
    d=dict(ACTIONS)[a]
    sides=[(0,1),(0,-1)] if d[0] else [(1,0),(-1,0)]
    out=defaultdict(float)
    for p,move in [(1-2*slip,d),(slip,sides[0]),(slip,sides[1])]: out[step(s,move)]+=p
    return out.items()

def score(s,n,step_reward): return TERMINALS.get(n,step_reward)

def best(s,v,step_reward,gamma,slip):
    return max(ACTIONS,key=lambda item:sum(p*(score(s,n,step_reward)+gamma*v[n]) for n,p in transitions(s,item[0],slip)))[0]

def value_iteration(step_reward=-.04,gamma=.95,slip=.1,tol=1e-10):
    v={s:0.0 for s in STATES}; sweeps=0
    while True:
        new=v.copy()
        for s in STATES:
            new[s]=max(sum(p*(score(s,n,step_reward)+gamma*v[n]) for n,p in transitions(s,a,slip)) for a,_ in ACTIONS)
        sweeps+=1
        if max(abs(new[s]-v[s]) for s in STATES)<tol: return new,{s:best(s,new,step_reward,gamma,slip) for s in STATES},sweeps
        v=new

def policy_iteration(step_reward=-.04,gamma=.95,slip=.1,tol=1e-10):
    policy={s:'U' for s in STATES}; evaluations=updates=rounds=0
    while True:
        v={s:0.0 for s in STATES}
        while True:
            new=v.copy()
            for s in STATES: new[s]=sum(p*(score(s,n,step_reward)+gamma*v[n]) for n,p in transitions(s,policy[s],slip))
            evaluations+=1; updates+=len(STATES)
            if max(abs(new[s]-v[s]) for s in STATES)<tol: v=new; break
            v=new
        new_policy={s:best(s,v,step_reward,gamma,slip) for s in STATES}; rounds+=1
        if new_policy==policy: return v,policy,rounds,evaluations,updates
        policy=new_policy

def grid(data,fmt):
    for y in range(H-1,-1,-1): print(' '.join('wall' if (x,y)==WALL else fmt(data[(x,y)]) for x in range(W)))

def negative_probability(policy,slip):
    p={s:float(s==(3,1)) for s in STATES}
    for _ in range(10000):
        q={s:sum(a*p[n] for n,a in transitions(s,policy[s],slip)) for s in STATES}
        if max(abs(q[s]-p[s]) for s in STATES)<1e-12:return q[(0,0)]
        p=q

def algo1():
    """run value iteration and print its output."""
    v,p,vs=value_iteration()
    print('\n=== algo1: value iteration ===')
    print('values');grid(v,lambda x:f'{x:.3f}')
    print('policy');grid(p,str)
    print('sweeps:',vs,'start:',round(v[(0,0)],6))
    return v,p

def algo2():
    """run policy iteration and print its output."""
    q,r,rounds,es,updates=policy_iteration()
    print('\n=== algo2: policy iteration ===')
    print('values');grid(q,lambda x:f'{x:.3f}')
    print('policy');grid(r,str)
    print('improvement rounds:',rounds,'evaluation sweeps:',es,'value updates:',updates,'start:',round(q[(0,0)],6))
    return q,r

def ex1():
    print('\n=== ex1: step reward and discount sweeps ===')
    print('step reward: reward, policy, start value, sweeps')
    for z in [-.01,-.04,-.1,-.5,-2.0]:
        x,a,n=value_iteration(step_reward=z);print(z,''.join(a[s] for s in STATES),round(x[(0,0)],4),n)
    print('discount: discount, policy, start value, sweeps')
    for z in [.5,.7,.9,.95,.99]:
        x,a,n=value_iteration(gamma=z);print(z,''.join(a[s] for s in STATES),round(x[(0,0)],4),n)

def ex2():
    print('\n=== ex2: slip probability sweep ===')
    print('slip, policy, start value, negative-terminal probability')
    for z in [0,.05,.1,.2,.3]:
        x,a,n=value_iteration(slip=z);print(z,''.join(a[s] for s in STATES),round(x[(0,0)],4),round(negative_probability(a,z),6))

def main():
    v,p=algo1(); q,r=algo2()
    print('\ncomparison: same policy =',p==r,'same values =',max(abs(v[s]-q[s]) for s in STATES)<1e-7)
    ex1(); ex2()

if __name__=='__main__': main()
