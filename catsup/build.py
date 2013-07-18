#coding=utf-8
import os
import copy
import shutil
import time
import hashlib
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from catsup.options import config, g
from catsup.reader import load_posts
from catsup.logger import logger
from catsup.utils import Pagination, call


def load_filters():
    def static_url(file):

        def get_hash(path):
            path = os.path.join(g.theme.path, 'static', path)
            if not os.path.exists(path):
                logger.warn("%s does not exist." % path)
                return ''

            with open(path, 'r') as f:
                return hashlib.md5(f.read()).hexdigest()[:4]

        hsh = get_hash(file)

        return '%s/%s?v=%s' % (config.config.static_prefix, file, hsh)

    def xmldatetime(t):
        t = time.gmtime(t)
        updated_xml = time.strftime('%Y-%m-%dT%H:%M:%SZ', t)
        return updated_xml

    def capitalize(str):
        return str.capitalize()

    g.jinja.globals["static_url"] = static_url
    g.jinja.filters["xmldatetime"] = xmldatetime
    g.jinja.filters["capitalize"] = capitalize


def load_theme_filters(theme):
    filters_file = os.path.join(theme.path, 'filters.py')
    if not os.path.exists(filters_file):
        return
    filters = {}
    execfile(filters_file, {}, filters)
    g.jinja.filters.update(filters)


def load_jinja():
    theme_path = os.path.join(g.theme.path, 'templates')
    g.jinja = Environment(
        loader=FileSystemLoader([theme_path, g.public_templates_path]),
        autoescape=False)

    g.jinja.globals["site"] = config.site
    g.jinja.globals["config"] = config.config
    g.jinja.globals["author"] = config.author
    g.jinja.globals["comment"] = config.comment
    g.jinja.globals["theme"] = config.theme.vars
    g.jinja.globals["g"] = g

    load_filters()


def write(filename, content):
    filename = os.path.join(config.config.output, filename.lstrip('/'))
    if filename.endswith('/'):
        filename += 'index.html'
    else:
        logger.info(filename)
    path = os.path.dirname(filename)
    if not os.path.exists(path):
        os.makedirs(path)
    with open(filename, 'w') as f:
        f.write(content)


def build_feed():
    logger.info('Generating atom')
    page = g.jinja.get_template('feed.xml').render()
    write('feed.xml', page)


def build_posts():
    logger.info('Start generating posts')
    template = g.jinja.get_template('post.html')
    posts = copy.copy(g.posts)
    posts.reverse()
    prev = None
    post = posts.pop()
    next = len(posts) and posts.pop() or None
    while post:
        logger.info('Generating %s' % post.filename)
        page = template.render(post=post, prev=prev,
            next=next)
        write(post.permalink, page)
        prev, post, next = post, next, len(posts) and posts.pop() or None


def build_pages():
    logger.info('Start generating pages')
    template = g.jinja.get_template('page.html')

    pages_path = os.path.join(config.config.output, 'page')

    if os.path.exists(pages_path):
        shutil.rmtree(pages_path)

    os.makedirs(pages_path)

    pagination = Pagination(1)
    while True:
        logger.info('Start generating page %s' % pagination.page)
        page = template.render(pagination=pagination)
        pager_file = os.path.join('page', "%s.html" % pagination.page)
        write(pager_file, page)
        if pagination.has_next:
            pagination = Pagination(pagination.next_num)
        else:
            break

    if not g.theme.has_index:
        page_1 = os.path.join(config.config.output, 'page', '1.html')
        index = os.path.join(config.config.output, 'index.html')
        os.rename(page_1, index)


def build_tags():
    try:
        template = g.jinja.get_template('tag.html')
    except TemplateNotFound:
        # Maybe the theme doesn't need this.
        return

    logger.info('Start generating tag pages')

    tags_path = os.path.join(config.config.output, 'tag')

    if os.path.exists(tags_path):
        shutil.rmtree(tags_path)

    os.makedirs(tags_path)

    prev = None
    for i, tag in enumerate(g.tags):
        logger.info('Generating tag %s' % tag.name)
        i += 1
        next = i < len(g.tags) and g.tags[i] or None
        page = template.render(tag=tag, prev=prev,
            next=next)
        write(tag.permalink, page)
        prev = tag


def build_archives():
    try:
        template = g.jinja.get_template('archive.html')
    except TemplateNotFound:
        # Maybe the theme doesn't need this.
        return
    logger.info('Start generating archive pages')

    archives_path = os.path.join(config.config.output, 'archive')

    if os.path.exists(archives_path):
        shutil.rmtree(archives_path)

    os.makedirs(archives_path)

    prev = None
    for i, archive in enumerate(g.archives):
        logger.info('Generating archive %s' % archive.name)
        i += 1
        next = i < len(g.archives) and g.archives[i] or None
        page = template.render(archive=archive, prev=prev,
            next=next)
        archive_file = os.path.join("archive", "%s.html" % archive.name)
        write(archive_file, page)
        prev = archive


def build_others():
    if not g.theme.pages:
        return
    logger.info('Start generating other pages')
    for file in g.theme.pages:
        logger.info('Generating %s' % file)
        template = g.jinja.get_template(file)
        page = template.render()
        write(file, page)


def copy_static():
    logger.info('Copying static files.')

    if os.path.exists(config.config.static):
        shutil.rmtree(config.config.static)

    shutil.copytree(os.path.join(g.theme.path, 'static'),
        config.config.static)

    favicon = os.path.join(config.config.source, 'favicon.ico')
    if not os.path.exists(favicon):
        favicon = os.path.join(g.theme.path, 'static', 'favicon.ico')
    if os.path.exists(favicon):
        shutil.copy(favicon, os.path.join(config.config.output,
            'favicon.ico'))

    robots = os.path.join(config.config.source, 'robots.txt')
    if not os.path.exists(robots):
        robots = os.path.join(g.theme.path, 'static', 'robots.txt')
    if os.path.exists(robots):
        shutil.copy(robots, os.path.join(config.config.output,
            'robots.txt'))

    logger.info('Done.')


def build():
    load_jinja()
    load_theme_filters(g.theme)
    logger.info('Building your blog..')
    t = time.time()
    load_posts()

    if not g.posts:
        logger.warning("No posts found.Stop building..")
        return

    if os.path.exists(config.config.output):
        cwd = os.path.abspath(config.config.output)
        call('rm -rf *', cwd=cwd)
    else:
        os.makedirs(config.config.output)

    build_feed()
    build_posts()
    build_pages()
    build_tags()
    build_archives()
    build_others()

    copy_static()

    logger.info('Finish building in %.3fs' % (time.time() - t))
