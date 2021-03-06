#coding:utf-8
import urllib2
import jieba
from BeautifulSoup import *
from urlparse import urljoin
from pysqlite2 import dbapi2 as sqlite

ignorewords=set(['the','of','to','and','a','in','is','it'])
class crawler:
    #初始化crawler并传入数据库名字
    def __init__(self,dbname):
        self.con=sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def dbcommit(self):
        self.con.commit()

    #5.2该函数的作用是返回某一条条目的ID，如果这一个条目不存在，程序就在数据库创建一条记录，将ID返回
    def getentryid(self,table,field,value,createnew=True):
        cur = self.con.execute(
            "select rowid from %s where %s = '%s'" % (table, field, value))
        res = cur.fetchone()
        if res == None:
            cur = self.con.execute(
            "insert into %s (%s) values ('%s')" % (table, field, value))
            return cur.lastrowid
        else:
            return res[0]

    #5：加入索引
    def addtoindex(self,url,soup):
        if self.isindexed(url): return
        print 'Indexing ' + url

        #获取每个单词
        text = self.gettextonly(soup)
        words = self.separatewords(text)

        # 获取URL的id
        urlid = self.getentryid('urllist', 'url', url)

        # 将每一个单词和URL关联
        for i in range(len(words)):
            word = words[i]
            if word in ignorewords: continue
            wordid = self.getentryid('wordlist', 'word', word)
            self.con.execute("insert into wordlocation(urlid,wordid,location) values (%d,%d,%d)" % (urlid, wordid, i))

    #3:从一个Html网页中提取文字（不带标签的）
    def gettextonly(self,soup):
         v = soup.string
        if v == None:
            c = soup.contents
            resulttext = ''
            for t in c:
                subtext = self.gettextonly(t)
                resulttext += subtext + '\n'
            return resulttext
        else:
            return v.strip()

    #4:根据任何非空白字符进行分词处理
    def separatewords(self,text):#这里我们不按照书本，因为书本是用于英文的分词，不大适合中文分词
        text = text.strip()
        content_seg = jieba.cut(text)
        return [" ".join(content_seg)]

    #5.3如果url已经建过索引，返回true
    def isindexed(self,url):
        u = self.con.execute("select rowid from urllist where url ='%s'"%url).fetchone()
        if u !=None:
            #检查它是否已经被检索过
            v=self.con.execute('select * from wordlocation where urlid=%d'%u[0]).fetchone()
            if v!=None:return True
        return False

    #添加一个关联两个网页的连接
    def addlinkref(self,urlFrom,urlTo,linkText):
        pass
    #1：从一组小网页开始进行广度优先搜索，直到某一给定深度，期间为网页建立索引
    def crawl(self,pages,depth=2):
        for i in range(depth):
            newpages=set()
            for page in pages:#进行广度优先遍历
                try:
                    c=urllib2.urlopen(page)
                except:
                    print "Can not open %s"%page
                    continue
                soup=BeautifulSoup(c.read())
                self.addtoindex(page,soup)

                links=soup('a')
                for link in links:
                    if('href' in dict(link.attrs)):
                        url =urljoin(page,link['href'])
                        if url.find("'") != -1: continue
                        url = url.split('#')[0]
                        if url[0:4] == 'http' and not self.isindexed(url):
                            newpages.add(url)
                        linkText = self.gettextonly(link)
                        self.addlinkref(page, url, linkText)

                self.dbcommit()

            pages = newpages



    #2:创建数据库表
    def createindextables(self):
        self.con.execute('create table urllist(url)')#urllist保存的是已经过索引的URL列表
        self.con.execute('create table wordlist(word)')#wordlist保存的是单词列表
        self.con.execute('create table wordlocation(urlid,wordid,location)')#wordlocation保存的是单词在文档当中的位置列表
        self.con.execute('create table link(fromid integer,toid integer)')#link保存两个URLID，指明从一张表格到另一张表格的链接关系
        self.con.execute('create table linkwords(wordid,linkid)')
        self.con.execute('create index wordidx on wordlist(word)')#建立这些index的目的是为了加快索引速度
        self.con.execute('create index urlidx on urllist(url)')
        self.con.execute('create index wordurlidx on wordlocation(wordid)')
        self.con.execute('create index urltoidx on link(toid)')
        self.con.execute('create index urlfromidx on link(fromid)')
        self.dbcommit()
        
        # pagerank算法
    def calculatepagerank(self, iterations=20):
        # 清除当前的pagerank
        self.con.execute('drop table if exists pagerank')
        self.con.execute('create table pagerank(urlid primary key,score)')

        # 初始化每一个url，令它等于1
        self.con.execute('insert into pagerank select rowid,1.0 from urllist')
        self.dbcommit()

        for i in range(iterations):
            print"Iteration %d" % (i)
            for (urlid,) in self.con.execute('select rowid from urllist'):
                pr = 0.15
                # 循环所有指向这个页面的外部链接
                for (linker,) in self.con.execute('select distinct fromid from link where toid=%d' % urlid):
                    linkingpr = self.con.execute('select score from pagerank where urlid=%d' % linker).fetchone()[0]

                    # 根据链接源，求得总的连接数
                    linkingcount = self.con.execute('select count(*) from link where fromid=%d' % linker).fetchone()[0]
                    pr += 0.85 * (linkingpr / linkingcount)
                self.con.execute('update pagerank set score=%f where urlid=%d' % (pr, urlid))
            self.dbcommit()

#第二部分：查询
#新建一个用于搜索的类
class searcher:
    def __init__(self,dbname):
        self.con = sqlite.connect(dbname)
    def __del__(self):
        self.con.close()

    def getmatchrows(self, q):
        # 构造查询的字符串
        fieldlist = 'w0.urlid'
        tablelist = ''
        clauselist = ''
        wordids = []

        # 根据空格拆分单词
        words = q.split(' ')
        tablenumber = 0

        for word in words:
            # Get the word ID
            wordrow = self.con.execute(
                "select rowid from wordlist where word='%s'" % word).fetchone()
            if wordrow != None:
                wordid = wordrow[0]
                wordids.append(wordid)
                if tablenumber > 0:
                    tablelist += ','
                    clauselist += ' and '
                    clauselist += 'w%d.urlid=w%d.urlid and ' % (tablenumber - 1, tablenumber)
                fieldlist += ',w%d.location' % tablenumber
                tablelist += 'wordlocation w%d' % tablenumber
                clauselist += 'w%d.wordid=%d' % (tablenumber, wordid)
                tablenumber += 1

        # Create the query from the separate parts
        fullquery = 'select %s from %s where %s' % (fieldlist, tablelist, clauselist)
        #print fullquery
        cur = self.con.execute(fullquery)
        rows = [row for row in cur]

        return rows, wordids

    # 基于内容的排序
    def getscoredlist(self, rows, wordids):
        totalscores = dict([row[0], 0] for row in rows)
        # 这里待会会补充评价函数的地方
        #weights = []
        #1:weights=[(1.0,self.frequencyscore(rows))]
       #2: weights = [(1.0, self.locationscore(rows))]
        #weights=[(1.0,self.frequencyscore(rows)),(1.5,self.locationscore(rows))]
        weights = [(1.0, self.distancescore(rows))]
        for (weight, scores) in weights:
            for url in totalscores:
                totalscores[url] += weight * scores[url]
        return totalscores

    def geturlname(self, id):
        return self.con.execute("select url from urllist where rowid="
                                "%d" % id).fetchone()[0]

    def query(self, q):
        rows, wordids = self.getmatchrows(q)
        scores = self.getscoredlist(rows, wordids)
        rankedscores = sorted([(score, url) for (url, score) in scores.items()], reverse=1)
        for (score, urlid) in rankedscores[0:10]:
            print'%f\t%s' % (score, self.geturlname(urlid))
    #定义一个归一化函数，这个函数是将我们的评分值变成0-1之间
    def normalizescores(self, scores, smallIsBetter=0):
        vsmall = 0.00001  # Avoid division by zero errors
        if smallIsBetter:
            minscore = min(scores.values())
            return dict([(u, float(minscore) / max(vsmall, l)) for (u, l) in scores.items()])
        else:
            maxscore = max(scores.values())
            if maxscore == 0: maxscore = vsmall
            return dict([(u, float(c) / maxscore) for (u, c) in scores.items()])

    def frequencyscore(self,rows):
        counts=dict([(row[0],0) for row in rows])
        for row in rows:
            counts[row[0]]+=1
        return self.normalizescores(counts)

    def locationscore(self,rows):
        location=dict([(row[0],100000) for row in rows])
        for row in rows:
            loca=sum(row[1:])
            if loca<location[row[0]]:location[row[0]] = loca

        return self.normalizescores(location,1)

    def distancescore(self, rows):
        # 如果只有一个单词，大家得分都一样
        if len(rows[0]) <= 2: return dict([(row[0], 1.0) for row in rows])
        mindistance = dict([(row[0], 1000000) for row in rows])

        for row in rows:
            dist = sum([abs(row[i] - row[i - 1]) for i in range(2, len(row))])
            if dist < mindistance[row[0]]: mindistance[row[0]] = dist
        return self.normalizescores(mindistance, smallIsBetter=1)

    #利用外部回指连接
    def inboundlinkscore(self, rows):
        uniqueurls = dict([(row[0], 1) for row in rows])
        inboundcount = dict(
            [(u, self.con.execute('select count(*) from link where toid=%d' % u).fetchone()[0]) for u in uniqueurls])
        return self.normalizescores(inboundcount
