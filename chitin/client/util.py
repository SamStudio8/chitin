import hashlib
import math
from datetime import datetime
import os
from . import conf
import syslog
syslog.openlog('chitind')

def get_node(path):
    for k in sorted(conf.ROOTS, key=len, reverse=True):
        if path.startswith(k):
            return (path.replace(k, ''), conf.ROOTS[k])
    return None

def hashfile(path, start_clock, halg=hashlib.md5, bs=65536, force_hash=False, partial_limit=10737418240, partial_sample=0.2):
    start_time = datetime.now()

    hashed=False
    mod_time = os.path.getmtime(path)

    # This seems to be causing more trouble than anything else, so just hash everything for now
    # Best thing to do is probably attempt to fire a GET at the server and see if we have the last seen date
    #if mod_time >= int(start_clock.strftime("%s")) or force_hash:
    #    pass
    #else:
    #    # The file /probably/ hasn't change, so don't bother rehashing...
    #    ret = 'U'

    # For files less than partial_limit, just get on with it
    b_hashed = 0
    if os.path.getsize(path) <= partial_limit:
        f = open(path, 'rb')
        buff = f.read(bs)
        halg = halg()
        halg.update(buff)
        b_hashed = bs
        while len(buff) > 0:
            buff = f.read(bs)
            halg.update(buff)
            b_hashed += bs
        f.close()
        hashed=True
    else:
        # I want to ensure no hashing process takes longer than 5 minutes
        # Caveat: The longer the file is, the more sparse the samples are
        # NOTE This is probably a fucking terrible idea

        # Assuming a total of partial_sample bytes to sample for the hash,
        # find the skip size needed to evenly sample the file with bs blocks
        body_sample_size = 5.243e+8 # 500MiB
        ends_sample_size = 2.147e+9 # 2GiB
        body_consec_samples = math.ceil(body_sample_size/bs)
        ends_consec_samples = math.ceil(ends_sample_size/bs)

        file_size_body = int(os.path.getsize(path) - ((2*ends_sample_size) + (2*body_sample_size)))
        body_num_samples = int( (file_size_body * partial_sample) / body_sample_size) # number of body samples needed
        body_seek_size = int(file_size_body / body_num_samples)

        # Read the first blocks
        f = open(path, 'rb')
        halg = halg()
        for i in range(ends_consec_samples):
            buff = f.read(bs)
            halg.update(buff)
            b_hashed += bs

        # Now seek to the evenly distributed sample points across the body
        pos = f.tell() + body_sample_size
        for i in range(body_num_samples):
            f.seek(int(pos))
            for i in range(body_consec_samples):
                buff = f.read(bs)
                halg.update(buff)
                b_hashed += bs
            pos = f.tell() + body_seek_size

        f.seek(int(os.path.getsize(path) - ends_sample_size))
        while len(buff) > 0:
            buff = f.read(bs)
            halg.update(buff)
            b_hashed += bs
        f.close()
        hashed=True

    ret = '0'
    if hashed:
        ret = halg.hexdigest()

    end_time = datetime.now()
    hash_time = end_time - start_time
    syslog.syslog('Hashed %s (~%.2fGB of %.2fGB in %s)' % (path, float(b_hashed) / 1e+9, float(os.path.getsize(path)) / 1e+9, str(hash_time)))

    return ret

