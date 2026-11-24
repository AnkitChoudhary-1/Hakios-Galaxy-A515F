// IrisPostCell.m - Feed post cell implementation
#import "IrisPostCell.h"
#import "IrisTheme.h"

@interface IrisPostCell ()

@property (nonatomic, strong) IrisPost *post;

// Header
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *usernameLabel;
@property (nonatomic, strong) UILabel *locationLabel;
@property (nonatomic, strong) UIButton *moreButton;

// Media
@property (nonatomic, strong) UIImageView *mediaImageView;

// Action bar
@property (nonatomic, strong) UIButton *likeButton;
@property (nonatomic, strong) UIButton *commentButton;
@property (nonatomic, strong) UIButton *shareButton;
@property (nonatomic, strong) UIButton *bookmarkButton;

// Metadata
@property (nonatomic, strong) UILabel *likesLabel;
@property (nonatomic, strong) UILabel *captionLabel;
@property (nonatomic, strong) UILabel *hashtagsLabel;
@property (nonatomic, strong) UIButton *commentsPreviewButton;
@property (nonatomic, strong) UILabel *timestampLabel;

@property (nonatomic, strong) UIView *bottomSpacer;

@end

@implementation IrisPostCell

- (instancetype)initWithStyle:(UITableViewCellStyle)style reuseIdentifier:(NSString *)reuseIdentifier {
    self = [super initWithStyle:style reuseIdentifier:reuseIdentifier];
    if (self) {
        self.selectionStyle = UITableViewCellSelectionStyleNone;
        [self setupSubviews];
    }
    return self;
}

- (void)setupSubviews {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.contentView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // 1. Header
    self.avatarImageView = [[UIImageView alloc] init];
    self.avatarImageView.layer.cornerRadius = 18.0;
    self.avatarImageView.layer.masksToBounds = YES;
    self.avatarImageView.userInteractionEnabled = YES;
    UITapGestureRecognizer *avatarTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(userTapped)];
    [self.avatarImageView addGestureRecognizer:avatarTap];
    [self.contentView addSubview:self.avatarImageView];
    
    self.usernameLabel = [[UILabel alloc] init];
    self.usernameLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightSemibold];
    self.usernameLabel.userInteractionEnabled = YES;
    UITapGestureRecognizer *userTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(userTapped)];
    [self.usernameLabel addGestureRecognizer:userTap];
    [self.contentView addSubview:self.usernameLabel];
    
    self.locationLabel = [[UILabel alloc] init];
    self.locationLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
    [self.contentView addSubview:self.locationLabel];
    
    self.moreButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.moreButton addTarget:self action:@selector(moreTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.moreButton];
    
    // 2. Media Image
    self.mediaImageView = [[UIImageView alloc] init];
    self.mediaImageView.contentMode = UIViewContentModeScaleAspectFill;
    self.mediaImageView.layer.masksToBounds = YES;
    self.mediaImageView.userInteractionEnabled = YES;
    UITapGestureRecognizer *mediaTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(mediaTapped)];
    [self.mediaImageView addGestureRecognizer:mediaTap];
    [self.contentView addSubview:self.mediaImageView];
    
    // 3. Action buttons
    self.likeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.likeButton addTarget:self action:@selector(likeTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.likeButton];
    
    self.commentButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.commentButton addTarget:self action:@selector(commentTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.commentButton];
    
    self.shareButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.shareButton addTarget:self action:@selector(shareTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.shareButton];
    
    self.bookmarkButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.bookmarkButton addTarget:self action:@selector(bookmarkTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.bookmarkButton];
    
    // 4. Metadata
    self.likesLabel = [[UILabel alloc] init];
    self.likesLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
    [self.contentView addSubview:self.likesLabel];
    
    self.captionLabel = [[UILabel alloc] init];
    self.captionLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightRegular];
    self.captionLabel.numberOfLines = 3;
    [self.contentView addSubview:self.captionLabel];
    
    self.hashtagsLabel = [[UILabel alloc] init];
    self.hashtagsLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    [self.contentView addSubview:self.hashtagsLabel];
    
    self.commentsPreviewButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.commentsPreviewButton.contentHorizontalAlignment = UIControlContentHorizontalAlignmentLeft;
    self.commentsPreviewButton.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightRegular];
    [self.commentsPreviewButton addTarget:self action:@selector(commentTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.commentsPreviewButton];
    
    self.timestampLabel = [[UILabel alloc] init];
    self.timestampLabel.font = [UIFont systemFontOfSize:10 weight:UIFontWeightRegular];
    [self.contentView addSubview:self.timestampLabel];
    
    self.bottomSpacer = [[UIView alloc] init];
    [self.contentView addSubview:self.bottomSpacer];
    
    [self updateTheme];
}

- (void)configureWithPost:(IrisPost *)post {
    _post = post;
    
    self.usernameLabel.text = post.username;
    self.locationLabel.text = post.location;
    self.locationLabel.hidden = (post.location.length == 0);
    
    // Set avatars and media safely using offline procedural photographic assets
    self.avatarImageView.image = [IrisData imageForKey:post.avatar
                                                  size:CGSizeMake(36, 36)
                                                 title:[post.username uppercaseString]
                                              subtitle:@""];
    
    CGFloat screenW = [UIScreen mainScreen].bounds.size.width;
    CGFloat mediaH = screenW * (post.aspectRatio > 0 ? (1.0 / post.aspectRatio) : 1.0);
    self.mediaImageView.image = [IrisData imageForKey:post.imageKey
                                                 size:CGSizeMake(screenW, mediaH)
                                                title:post.location
                                             subtitle:post.username];
    
    // Metadata
    NSNumberFormatter *fmt = [[NSNumberFormatter alloc] init];
    fmt.numberStyle = NSNumberFormatterDecimalStyle;
    NSString *likesStr = [fmt stringFromNumber:@(post.likes)];
    self.likesLabel.text = [NSString stringWithFormat:@"%@ likes", likesStr];
    
    // Attributed caption: Bold username + caption
    NSMutableAttributedString *attr = [[NSMutableAttributedString alloc] initWithString:[NSString stringWithFormat:@"%@  %@", post.username, post.caption]];
    [attr addAttribute:NSFontAttributeName value:[UIFont systemFontOfSize:13 weight:UIFontWeightBold] range:NSMakeRange(0, post.username.length)];
    [attr addAttribute:NSForegroundColorAttributeName value:[[IrisTheme sharedTheme] primaryTextColor] range:NSMakeRange(0, attr.length)];
    self.captionLabel.attributedText = attr;
    
    self.hashtagsLabel.text = post.hashtags;
    
    NSString *commentText = [NSString stringWithFormat:@"View all %ld comments", (long)post.commentsCount];
    [self.commentsPreviewButton setTitle:commentText forState:UIControlStateNormal];
    
    self.timestampLabel.text = [post.timestamp uppercaseString];
    
    [self updateActionButtonsAnimated:NO];
    [self updateTheme];
    [self setNeedsLayout];
}

- (void)updateActionButtonsAnimated:(BOOL)animated {
    UIColor *primaryColor = [[IrisTheme sharedTheme] primaryTextColor];
    UIColor *likeColor = self.post.isLiked ? [[IrisTheme sharedTheme] errorColor] : primaryColor;
    UIColor *bookmarkColor = self.post.isBookmarked ? [[IrisTheme sharedTheme] accentVioletColor] : primaryColor;
    
    UIImage *likeImg = [IrisTheme iconNamed:@"like" size:CGSizeMake(24, 24) color:likeColor filled:self.post.isLiked];
    UIImage *commentImg = [IrisTheme iconNamed:@"comment" size:CGSizeMake(24, 24) color:primaryColor filled:NO];
    UIImage *shareImg = [IrisTheme iconNamed:@"share" size:CGSizeMake(24, 24) color:primaryColor filled:NO];
    UIImage *bookmarkImg = [IrisTheme iconNamed:@"bookmark" size:CGSizeMake(24, 24) color:bookmarkColor filled:self.post.isBookmarked];
    
    [self.likeButton setImage:likeImg forState:UIControlStateNormal];
    [self.commentButton setImage:commentImg forState:UIControlStateNormal];
    [self.shareButton setImage:shareImg forState:UIControlStateNormal];
    [self.bookmarkButton setImage:bookmarkImg forState:UIControlStateNormal];
    
    if (animated && self.post.isLiked) {
        // Subtle bounce animation for like
        self.likeButton.transform = CGAffineTransformMakeScale(1.3, 1.3);
        [UIView animateWithDuration:0.2 animations:^{
            self.likeButton.transform = CGAffineTransformIdentity;
        }];
    }
}

- (void)updateTheme {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.contentView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    self.usernameLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.locationLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    self.likesLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.hashtagsLabel.textColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self.commentsPreviewButton setTitleColor:[[IrisTheme sharedTheme] secondaryTextColor] forState:UIControlStateNormal];
    self.timestampLabel.textColor = [[IrisTheme sharedTheme] mutedTextColor];
    
    UIImage *moreImg = [IrisTheme iconNamed:@"more" size:CGSizeMake(20, 20) color:[[IrisTheme sharedTheme] secondaryTextColor] filled:NO];
    [self.moreButton setImage:moreImg forState:UIControlStateNormal];
    
    [self updateActionButtonsAnimated:NO];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    
    CGFloat w = self.contentView.bounds.size.width;
    CGFloat y = 8.0;
    
    // Header
    self.avatarImageView.frame = CGRectMake(14, y, 36, 36);
    if (self.post.location.length > 0) {
        self.usernameLabel.frame = CGRectMake(58, y, w - 110, 18);
        self.locationLabel.frame = CGRectMake(58, y + 18, w - 110, 15);
    } else {
        self.usernameLabel.frame = CGRectMake(58, y + 8, w - 110, 20);
    }
    self.moreButton.frame = CGRectMake(w - 44, y + 2, 36, 32);
    
    y += 46.0;
    
    // Media
    CGFloat mediaH = w * (self.post.aspectRatio > 0 ? (1.0 / self.post.aspectRatio) : 1.0);
    self.mediaImageView.frame = CGRectMake(0, y, w, mediaH);
    
    y += mediaH + 8.0;
    
    // Action bar
    CGFloat btnW = 38.0;
    CGFloat btnH = 32.0;
    self.likeButton.frame = CGRectMake(12, y, btnW, btnH);
    self.commentButton.frame = CGRectMake(12 + btnW, y, btnW, btnH);
    self.shareButton.frame = CGRectMake(12 + btnW * 2, y, btnW, btnH);
    self.bookmarkButton.frame = CGRectMake(w - 14 - btnW, y, btnW, btnH);
    
    y += btnH + 6.0;
    
    // Likes
    self.likesLabel.frame = CGRectMake(14, y, w - 28, 18);
    y += 22.0;
    
    // Caption
    CGSize capSize = [self.captionLabel sizeThatFits:CGSizeMake(w - 28, CGFLOAT_MAX)];
    self.captionLabel.frame = CGRectMake(14, y, w - 28, capSize.height);
    y += capSize.height + 4.0;
    
    // Hashtags
    if (self.post.hashtags.length > 0) {
        self.hashtagsLabel.frame = CGRectMake(14, y, w - 28, 16);
        y += 20.0;
    }
    
    // Comments preview
    self.commentsPreviewButton.frame = CGRectMake(14, y, w - 28, 18);
    y += 22.0;
    
    // Timestamp
    self.timestampLabel.frame = CGRectMake(14, y, w - 28, 14);
    y += 24.0;
    
    self.bottomSpacer.frame = CGRectMake(0, y, w, 8.0);
}

+ (CGFloat)heightForPost:(IrisPost *)post width:(CGFloat)width {
    CGFloat y = 8.0 + 46.0; // Header
    CGFloat mediaH = width * (post.aspectRatio > 0 ? (1.0 / post.aspectRatio) : 1.0);
    y += mediaH + 8.0; // Media
    y += 32.0 + 6.0; // Actions
    y += 22.0; // Likes
    
    // Caption measurement
    NSString *full = [NSString stringWithFormat:@"%@  %@", post.username, post.caption];
    CGRect capRect = [full boundingRectWithSize:CGSizeMake(width - 28, CGFLOAT_MAX)
                                        options:NSStringDrawingUsesLineFragmentOrigin
                                     attributes:@{NSFontAttributeName: [UIFont systemFontOfSize:13]}
                                        context:nil];
    y += MIN(capRect.size.height + 4.0, 60.0);
    
    if (post.hashtags.length > 0) {
        y += 20.0;
    }
    y += 22.0; // Comments preview
    y += 24.0; // Timestamp
    y += 12.0; // Bottom pad
    
    return ceil(y);
}

#pragma mark - User Actions

- (void)userTapped {
    if ([self.delegate respondsToSelector:@selector(postCell:didTapUser:)]) {
        [self.delegate postCell:self didTapUser:self.post.username];
    }
}

- (void)mediaTapped {
    if ([self.delegate respondsToSelector:@selector(postCell:didTapMediaForPost:)]) {
        [self.delegate postCell:self didTapMediaForPost:self.post];
    }
}

- (void)likeTapped {
    [[IrisData sharedData] toggleLikeForPost:self.post];
    NSNumberFormatter *fmt = [[NSNumberFormatter alloc] init];
    fmt.numberStyle = NSNumberFormatterDecimalStyle;
    self.likesLabel.text = [NSString stringWithFormat:@"%@ likes", [fmt stringFromNumber:@(self.post.likes)]];
    [self updateActionButtonsAnimated:YES];
    
    if ([self.delegate respondsToSelector:@selector(postCell:didTapLikeForPost:)]) {
        [self.delegate postCell:self didTapLikeForPost:self.post];
    }
}

- (void)commentTapped {
    if ([self.delegate respondsToSelector:@selector(postCell:didTapCommentForPost:)]) {
        [self.delegate postCell:self didTapCommentForPost:self.post];
    }
}

- (void)shareTapped {
    if ([self.delegate respondsToSelector:@selector(postCell:didTapShareForPost:)]) {
        [self.delegate postCell:self didTapShareForPost:self.post];
    }
}

- (void)bookmarkTapped {
    [[IrisData sharedData] toggleBookmarkForPost:self.post];
    [self updateActionButtonsAnimated:NO];
    
    if ([self.delegate respondsToSelector:@selector(postCell:didTapBookmarkForPost:)]) {
        [self.delegate postCell:self didTapBookmarkForPost:self.post];
    }
}

- (void)moreTapped {
    if ([self.delegate respondsToSelector:@selector(postCell:didTapMoreForPost:)]) {
        [self.delegate postCell:self didTapMoreForPost:self.post];
    }
}

@end
