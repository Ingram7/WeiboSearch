# -*- coding: utf-8 -*-
import scrapy
from scrapy import Request
from ..items import *
import datetime
import re


class WeiboSpiderSpider(scrapy.Spider):
    name = 'weibo_spider'
    allowed_domains = ['weibo.cn']
    # start_urls = ['http://weibo.cn/']
    base_url = "https://weibo.cn"
    def start_requests(self):

        url_format = "https://weibo.cn/search/mblog?hideSearchFrame=&keyword={}&advancedfilter=1&starttime={}&endtime={}&sort=time"

        # 搜索的关键词，可以修改

        # keyword = "阴阳师"
        keyword = "高考"

        # 搜索的起始日期，自行修改   微博的创建日期是2009-08-16 也就是说不要采用这个日期更前面的日期了
        date_start = datetime.datetime.strptime("2019-05-20", '%Y-%m-%d')
        # 搜索的结束日期，自行修改
        date_end = datetime.datetime.strptime("2019-06-20", '%Y-%m-%d')

        time_spread = datetime.timedelta(days=1)
        while date_start < date_end:
            next_time = date_start + time_spread
            url = url_format.format(keyword, date_start.strftime("%Y%m%d"), next_time.strftime("%Y%m%d"))
            date_start = next_time
            yield Request(url, callback=self.parse_tweet, dont_filter=True)


    # 解析微博
    def parse_tweet(self, response):
        """
        解析本页的数据
        """
        tweet_nodes = response.xpath('//div[@class="c" and @id]')
        for tweet_node in tweet_nodes:
            try:
                tweet_item = TweetsItem()

                tweet_repost_url = tweet_node.xpath('.//a[contains(text(),"转发[")]/@href').extract()[0]
                user_tweet_id = re.search(r'/repost/(.*?)\?uid=(\d+)', tweet_repost_url)

                # 微博URL
                tweet_item['weibo_url'] = 'https://weibo.com/{}/{}'.format(user_tweet_id.group(2), user_tweet_id.group(1))

                # 发表该微博用户id
                tweet_item['user_id'] = user_tweet_id.group(2)

                # 微博id
                tweet_item['id'] = '{}_{}'.format(user_tweet_id.group(2), user_tweet_id.group(1))

                create_time_info = ''.join(tweet_node.xpath('.//span[@class="ct"]').xpath('string(.)').extract())
                if "来自" in create_time_info:
                    # 微博发表时间
                    tweet_item['created_at'] = create_time_info.split('来自')[0].strip()
                    # 发布微博的工具
                    tweet_item['tool'] = create_time_info.split('来自')[1].strip()
                else:
                    tweet_item['created_at'] = create_time_info.strip()

                # 点赞数
                like_num = tweet_node.xpath('.//a[contains(text(),"赞[")]/text()').extract()[0]
                tweet_item['like_num'] = int(re.search('\d+', like_num).group())

                # 转发数
                repost_num = tweet_node.xpath('.//a[contains(text(),"转发[")]/text()').extract()[0]
                tweet_item['repost_num'] = int(re.search('\d+', repost_num).group())

                # 评论数
                comment_num = tweet_node.xpath(
                    './/a[contains(text(),"评论[") and not(contains(text(),"原文"))]/text()').extract()[0]
                tweet_item['comment_num'] = int(re.search('\d+', comment_num).group())

                # 图片
                images = tweet_node.xpath('.//img[@alt="图片"]/@src')
                if images:
                    tweet_item['image_url'] = images.extract()[0]

                # 视频
                videos = tweet_node.xpath('.//a[contains(@href,"https://m.weibo.cn/s/video/show?object_id=")]/@href')
                if videos:
                    tweet_item['video_url'] = videos.extract()[0]

                # 定位信息
                map_node = tweet_node.xpath('.//a[contains(text(),"显示地图")]')
                if map_node:
                    tweet_item['location'] = True

                # 原始微博，只有转发的微博才有这个字段
                repost_node = tweet_node.xpath('.//a[contains(text(),"原文评论[")]/@href')
                if repost_node:
                    tweet_item['origin_weibo'] = repost_node.extract()[0]

                # 检测有没有阅读全文:
                all_content_link = tweet_node.xpath('.//a[text()="全文" and contains(@href,"ckAll=1")]')
                if all_content_link:
                    all_content_url = self.base_url + all_content_link.xpath('./@href').extract()[0]
                    yield Request(all_content_url, callback=self.parse_all_content, meta={'item': tweet_item},
                                  )
                else:
                    # 微博内容
                    tweet_item['content'] = \
                        ''.join(tweet_node.xpath('./div[1]').xpath('string(.)').extract()
                                ).replace(u'\xa0', '').replace(u'\u3000', '').replace(' ', '').split('赞[', 1)[0]

                    if 'location' in tweet_item:
                        tweet_item['location'] = tweet_node.xpath('.//span[@class="ctt"]/a[last()]/text()').extract()[0]
                    yield tweet_item

                # 抓取该微博的用户信息
                yield Request(url="https://weibo.cn/{}/info".format(tweet_item['user_id']),
                              callback=self.parse_information, priority=2)

            except Exception as e:
                self.logger.error(e)

        next_page = response.xpath('//div[@id="pagelist"]//a[contains(text(),"下页")]/@href')
        if next_page:
            url = self.base_url + next_page[0].extract()
            yield Request(url, callback=self.parse_tweet, dont_filter=True)

    def parse_all_content(self, response):
        # 有阅读全文的情况，获取全文
        tweet_item = response.meta['item']
        tweet_item['content'] = ''.join(response.xpath('//*[@id="M_"]/div[1]').xpath('string(.)').extract()
                                        ).replace(u'\xa0', '').replace(u'\u3000', '').replace(' ', '').split('赞[', 1)[0]
        if 'location' in tweet_item:
            tweet_item['location'] = \
            response.xpath('//*[@id="M_"]/div[1]//span[@class="ctt"]/a[last()]/text()').extract()[0]
        yield tweet_item




    def parse_information(self, response):
        """ 抓取个人信息 """
        information_item = InformationItem()

        information_item['id'] = re.findall('(\d+)/info', response.url)[0]
        # 获取标签里的所有text()
        information_text = ";".join(response.xpath('//div[@class="c"]//text()').extract())

        name = re.findall('昵称;?[：:]?(.*?);', information_text)
        if name and name[0]:
            information_item["name"] = name[0].replace(u"\xa0", "")

        gender = re.findall('性别;?[：:]?(.*?);', information_text)
        if gender and gender[0]:
            information_item["gender"] = gender[0].replace(u"\xa0", "")

        place = re.findall('地区;?[：:]?(.*?);', information_text)
        if place and place[0]:
            place = place[0].replace(u"\xa0", "").split()
            information_item["province"] = place[0]
            if len(place) > 1:
                information_item["city"] = place[1]

        briefIntroduction = re.findall('简介;?[：:]?(.*?);', information_text)
        if briefIntroduction and briefIntroduction[0]:
            information_item["brief_introduction"] = briefIntroduction[0].replace(u"\xa0", "")

        birthday = re.findall('生日;?[：:]?(.*?);', information_text)
        if birthday and birthday[0]:
            information_item['birthday'] = birthday[0]

        sex_orientation = re.findall('性取向;?[：:]?(.*?);', information_text)
        if sex_orientation and sex_orientation[0]:
            if sex_orientation[0].replace(u"\xa0", "") == gender[0]:
                information_item["sex_orientation"] = "同性恋"
            else:
                information_item["sex_orientation"] = "异性恋"

        sentiment = re.findall('感情状况;?[：:]?(.*?);', information_text)
        if sentiment and sentiment[0]:
            information_item["sentiment"] = sentiment[0].replace(u"\xa0", "")

        vip_level = re.findall('会员等级;?[：:]?(.*?);', information_text)
        if vip_level and vip_level[0]:
            information_item["vip_level"] = vip_level[0].replace(u"\xa0", "")

        authentication = re.findall('认证信息;?[：:]?(.*?);', information_text)
        if authentication and authentication[0]:
            information_item["authentication"] = authentication[0].replace(u"\xa0", "")

        labels = re.findall('标签;?[：:]?(.*?)更多>>', information_text)
        if labels and labels[0]:
            information_item["labels"] = labels[0].replace(u"\xa0", ",").replace(';', '').strip(',')

        yield Request(self.base_url + '/u/{}'.format(information_item['id']),
                      callback=self.parse_further_information,
                      meta={'item': information_item},
                      dont_filter=True, priority=1)

    def parse_further_information(self, response):

        information_item = response.meta['item']
        tweets_num = re.findall('微博\[(\d+)\]', response.text)
        if tweets_num:
            information_item['tweets_num'] = int(tweets_num[0])

        follows_num = re.findall('关注\[(\d+)\]', response.text)
        if follows_num:
            information_item['follows_num'] = int(follows_num[0])

        fans_num = re.findall('粉丝\[(\d+)\]', response.text)
        if fans_num:
            information_item['fans_num'] = int(fans_num[0])

        yield information_item
