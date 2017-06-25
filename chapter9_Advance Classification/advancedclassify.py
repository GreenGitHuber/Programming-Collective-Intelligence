#coding:utf-8
from pylab import *
class matchrow:
    def __init__(self,row,allnum=False):
        if allnum:
            self.data =[float(row[i]) for  i in range(len(row)-1)]
        else:
            self.data = row[0:len(row)-1]
        self.match=int(row[len(row) -1])

def loadmatch(f,allnum = False):
    rows=[]
    for line in file(f):
        rows.append(matchrow(line.split(','),allnum))
    return rows

def plotagematches (rows,averages):
    xm,ym=[r.data[0] for r in rows if r.match==1],[r.data[1] for r in rows if r.match==1]
    xn,yn=[r.data[0] for r in rows if r.match==0],[r.data[1] for r in rows if r.match==0]
    plot(xm,ym,'go')
    plot(xn,yn,'ro')
    xmd, ymd = averages[1][0], averages[1][1]
    xnd, ynd = averages[0][0], averages[0][1]
    plot(xmd, ymd, 'gx')
    plot(xnd, ynd, 'rx')


    show()

#基本的线性分类
def lineartrain(rows):
    averages={}
    counts={}

    for row in rows:
        cl = row.match
        averages.setdefault(cl,[0.0]*(len(row.data)))
        counts.setdefault(cl,0)
        for i in range(len(row.data)):
            averages[cl][i]+=row.data[i]
        counts[cl]+=1
    for cl,avg in averages.items():
        for i in range(len(avg)):
            avg[i]/=counts[cl]
    return averages
#向量点积
def dotproduct(v1,v2):
  return sum([v1[i]*v2[i] for i in range(len(v1))])

def dpclassify(point,avgs):
  b=(dotproduct(avgs[1],avgs[1])-dotproduct(avgs[0],avgs[0]))/2
  y=dotproduct(point,avgs[0])-dotproduct(point,avgs[1])+b
  if y>0: return 0
  else: return 1

def yesno(v):
  if v=='yes': return 1
  elif v=='no': return -1
  else: return 0

#兴趣列表
def matchcount(interest1, interest2):
    l1 = interest1.split(':')
    l2 = interest2.split(':')
    x = 0
    for v in l1:
        if v in l2: x += 1
    return x
#计算距离,因为我们无法使用Yahoo！Maps,所以就直接写了一个空函数
def milesdistance(a1,a2):
  return 0.1

#构造新的数据集，利用我们上面准备的数据处理方式
def loadnumerical():
  oldrows=loadmatch('matchmaker.csv')
  newrows=[]
  for row in oldrows:
    d=row.data
    data=[float(d[0]),yesno(d[1]),yesno(d[2]),
          float(d[5]),yesno(d[6]),yesno(d[7]),
          matchcount(d[3],d[8]),
          milesdistance(d[4],d[9]),
          row.match]
    newrows.append(matchrow(data))
  return newrows

#这里是书本当中写错的地方，我做了修改
def scaledata(rows):
    # low = 999999999.0
    # high = -999999999.0
    #找到每一行数据当中的最小最大值
    for row in rows:
        low = 999999999.0
        high = -999999999.0
        d = row.data
        for i in range(len(d)):
            if d[i] < low: low = d[i]
            if d[i] > high: high = d[i]


    # 对数据进行缩放处理的函数
    def scaleinput(d):
        return [(d[i] - low) / (high - low)#将结果减去最小值，这样值域的范围就变为以0为起点，除以最大值和最小值的差，就将所有的数据转化为介于0-1的值
                for i in range(len(d))]

    # 对所有的数据进行缩放处理
    newrows = [matchrow(scaleinput(row.data) + [row.match])
               for row in rows]

    #返回新的数据和缩放处理函数
    return newrows, scaleinput
#定义一个径向基函数，径向基函数和点积函数很相似，但是和点积函数不同的是径向基函数是一个非线性的
def rbf(v1,v2,gamma=10):
  dv=[v1[i]-v2[i] for i in range(len(v1))]
  l=sum(dv)
  return math.e**(-gamma*l)

#定义一个非线性分类器，采用了rbf
def nlclassify(point, rows, offset, gamma=10):
    sum0 = 0.0
    sum1 = 0.0
    count0 = 0
    count1 = 0

    for row in rows:
        if row.match == 0:
            sum0 += rbf(point, row.data, gamma)
            count0 += 1
        else:
            sum1 += rbf(point, row.data, gamma)
            count1 += 1
    y = (1.0 / count0) * sum0 - (1.0 / count1) * sum1 + offset

    if y > 0:
        return 0
    else:
        return 1


def getoffset(rows, gamma=10):
    l0 = []
    l1 = []
    for row in rows:
        if row.match == 0:
            l0.append(row.data)
        else:
            l1.append(row.data)
    sum0 = sum(sum([rbf(v1, v2, gamma) for v1 in l0]) for v2 in l0)
    sum1 = sum(sum([rbf(v1, v2, gamma) for v1 in l1]) for v2 in l1)

    return (1.0 / (len(l1) ** 2)) * sum1 - (1.0 / (len(l0) ** 2)) * sum0
