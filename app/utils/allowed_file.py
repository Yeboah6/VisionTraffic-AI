import os

def allowed_file(filename):
    """Check if the file extension is allowed"""
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'mp4', 'mov', 'avi', 'mkv'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_type(filename):
    """Determine if file is image or video"""
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}
    video_extensions = {'mp4', 'mov', 'avi', 'mkv'}
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in image_extensions:
        return 'image'
    elif ext in video_extensions:
        return 'video'
    else:
        return 'unknown'