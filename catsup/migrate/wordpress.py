import os
import sys
import logging
from xml.etree import ElementTree

from catsup.parser.config import get_template
from catsup.utils import to_unicode


def write_posts(items, folder):
    if os.path.exists(folder):
        import shutil
        shutil.rmtree(folder)
    os.makedirs(folder)

    def write(filename, lines):
        with open(os.path.join(folder, filename), 'w') as f:
            f.write(to_unicode('\n'.join(lines)))

    for item in items:
        if item.find('post_type').text != 'post':
            # Catsup supports post only.
            continue
        elif item.find('status').text != 'publish':
            continue

        tags = []
        category = []

        post = []

        title = to_unicode(item.find('title').text).strip()
        logging.info("Reading post %s" % title)
        post.append('# %s' % title)
        post.append('')

        for meta in item.findall('category'):
            if meta.get('domain') == 'category':
                category.append(meta.text.strip())
            elif meta.get('domain') == 'post_tag':
                tags.append(meta.text.strip())
        if tags:
            post.append('- tags: %s' % ', '.join(tags))
        if category:
            post.append('- category: %s' % ', '.join(category))

        if item.find('comment_status').text != 'open':
            post.append('- comment: disabled')

        post.append('')
        post.append('---')
        content = '{http://purl.org/rss/1.0/modules/content/}encoded'
        content = item.find(content).text
        post.append(content)

        title = title.replace(' ', '-').replace('/', '-').replace('\\', '-')

        filename = item.find('post_date').text[:10] + \
                   '-' + title + \
                   '.md'
        write(filename, post)


def migrate(filename, output):
    try:
        with open(filename) as f:
            xml = f.read().replace('creativeCommons:', '')
            xml = xml.replace('wp:', '')
            # Some plugin may output unvailed xml
            xml = ElementTree.fromstring(xml)
    except:
        logging.error("Unable to open wordpress output file %s" % filename)
        sys.exit(1)
    channel = xml.find('channel')

    items = channel.findall('item')
    items.reverse()
    write_posts(items,
                os.path.join(output, 'posts'))

    name = channel.find('title').text
    url = channel.find('link').text
    author = channel.find('author').find('author_display_name').text
    template = get_template()
    template.replace("blogname", name)
    template.replace("http://blog.com", url)
    template.replace("nickname", author)
    with open(os.path.join(output, 'config.json'), 'w') as f:
        f.write(template)

    logging.info("Migrate done.")
