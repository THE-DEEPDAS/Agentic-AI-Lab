import random

GAMES={
'prisoners dilemma':({'C','D'},{'C','D'},{('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}),
'stag hunt':({'S','H'},{'S','H'},{('S','S'):(4,4),('S','H'):(0,3),('H','S'):(3,0),('H','H'):(2,2)}),
'chicken':({'sw','st'},{'sw','st'},{('sw','sw'):(3,3),('sw','st'):(1,4),('st','sw'):(4,1),('st','st'):(0,0)}),
'matching pennies':({'H','T'},{'H','T'},{('H','H'):(1,-1),('H','T'):(-1,1),('T','H'):(-1,1),('T','T'):(1,-1)})}

def analyse(a,b,p):
    br1={y:{x for x in a if p[x,y][0]==max(p[z,y][0] for z in a)} for y in b}
    br2={x:{y for y in b if p[x,y][1]==max(p[x,z][1] for z in b)} for x in a}
    eq=[(x,y) for x in a for y in b if x in br1[y] and y in br2[x]]
    d1=[x for x in a if any(all(p[z,y][0]>p[x,y][0] for y in b) for z in a if z!=x)]
    d2=[y for y in b if any(all(p[x,z][1]>p[x,y][1] for x in a) for z in b if z!=y)]
    return d1,d2,eq

def action(name,own,other):
    if name=='always cooperate':return 'C'
    if name=='always defect':return 'D'
    if name=='tit for tat':return 'C' if not other else other[-1]
    if name=='grim trigger':return 'D' if 'D' in other else 'C'
    if name=='generous tit for tat':return 'C' if not other or other[-1]=='C' or random.random()<.1 else 'D'
    return random.choice('CD')

def tournament(noise=0,rounds=100,seeds=5):
    names=['always cooperate','always defect','tit for tat','grim trigger','generous tit for tat','random']; pay={('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}; matrix=[]
    for x in names:
        row=[]
        for y in names:
            total=0
            for seed in range(seeds):
                random.seed(seed); hx=[];hy=[]
                for _ in range(rounds):
                    a,b=action(x,hx,hy),action(y,hy,hx)
                    if random.random()<noise:a='D' if a=='C' else 'C'
                    if random.random()<noise:b='D' if b=='C' else 'C'
                    total+=pay[a,b][0];hx.append(a);hy.append(b)
            row.append(total/(seeds*rounds))
        matrix.append(row)
    return names,matrix,[sum(row)/len(row) for row in matrix]

def algo1():
    print('\n=== algo1: one-shot game analysis ===')
    mixed={'prisoners dilemma':(2/3,2/3),'stag hunt':(2/3,2/3),'chicken':(.5,.5),'matching pennies':(.5,.5)}
    for name,(a,b,p) in GAMES.items():print(name,'dominated:',analyse(a,b,p)[:2],'pure equilibria:',analyse(a,b,p)[2],'mixed equilibrium:',mixed[name])

def algo2():
    print('\n=== algo2: iterated prisoner dilemma tournament ===')
    names,m,means=tournament();print('\ntournament matrix')
    for n,row,mean in zip(names,m,means):print(n,[round(x,3) for x in row],'mean',round(mean,3))
    print('ranking:',[names[i] for i in sorted(range(len(names)),key=lambda i:means[i],reverse=True)])

def ex1():
    print('\n=== ex1: tournament with implementation noise ===')
    print('\nnoise sweep')
    for z in [0,.01,.05,.1]:
        n,_,means=tournament(z);print(z,dict(zip(n,[round(x,3) for x in means])))

def ex2():
    print('\n=== ex2: continuation probability ===')
    print('\ncontinuation probability')
    for w in [0,.2,.4,.6,.8,.9]:print(w,'tft/tft',3,'defect/tft',5*(1-w)+1*w)

def main():
    algo1();algo2();ex1();ex2()

if __name__=='__main__':main()
