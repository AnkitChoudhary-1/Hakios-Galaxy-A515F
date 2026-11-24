// IrisStoriesHeaderView.m - Horizontal stories row implementation
#import "IrisStoriesHeaderView.h"
#import "IrisTheme.h"

@interface IrisStoryItemView : UIView

@property (nonatomic, strong) IrisStory *story;
@property (nonatomic, strong) UIImageView *ringView;
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UIView *plusBadge;
@property (nonatomic, strong) UILabel *usernameLabel;
@property (nonatomic, copy) void (^tapHandler)(IrisStory *story);

- (void)configureWithStory:(IrisStory *)story;
- (void)updateTheme;

@end

@implementation IrisStoryItemView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        [self setupSubviews];
    }
    return self;
}

- (void)setupSubviews {
    CGFloat circleSize = 64.0;
    CGFloat avatarSize = 54.0;
    
    // Gradient or gray ring
    self.ringView = [[UIImageView alloc] initWithFrame:CGRectMake((self.bounds.size.width - circleSize) / 2.0, 4, circleSize, circleSize)];
    self.ringView.contentMode = UIViewContentModeScaleAspectFit;
    [self addSubview:self.ringView];
    
    // Avatar
    self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake((self.bounds.size.width - avatarSize) / 2.0, 4 + (circleSize - avatarSize) / 2.0, avatarSize, avatarSize)];
    self.avatarImageView.layer.cornerRadius = avatarSize / 2.0;
    self.avatarImageView.layer.masksToBounds = YES;
    self.avatarImageView.contentMode = UIViewContentModeScaleAspectFill;
    [self addSubview:self.avatarImageView];
    
    // Plus badge for Your Story
    CGFloat badgeSize = 18.0;
    self.plusBadge = [[UIView alloc] initWithFrame:CGRectMake(CGRectGetMaxX(self.avatarImageView.frame) - badgeSize + 2,
                                                              CGRectGetMaxY(self.avatarImageView.frame) - badgeSize + 2,
                                                              badgeSize, badgeSize)];
    self.plusBadge.layer.cornerRadius = badgeSize / 2.0;
    self.plusBadge.layer.borderWidth = 2.0;
    self.plusBadge.layer.borderColor = [[IrisTheme sharedTheme] mainBackgroundColor].CGColor;
    self.plusBadge.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    
    UILabel *plusIcon = [[UILabel alloc] initWithFrame:self.plusBadge.bounds];
    plusIcon.text = @"+";
    plusIcon.font = [UIFont systemFontOfSize:14 weight:UIFontWeightBold];
    plusIcon.textColor = [UIColor whiteColor];
    plusIcon.textAlignment = NSTextAlignmentCenter;
    [self.plusBadge addSubview:plusIcon];
    [self addSubview:self.plusBadge];
    
    // Username label
    self.usernameLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, CGRectGetMaxY(self.ringView.frame) + 4, self.bounds.size.width - 4, 16)];
    self.usernameLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
    self.usernameLabel.textAlignment = NSTextAlignmentCenter;
    self.usernameLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    [self addSubview:self.usernameLabel];
    
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleTap)];
    [self addGestureRecognizer:tap];
    self.userInteractionEnabled = YES;
}

- (void)configureWithStory:(IrisStory *)story {
    _story = story;
    
    if (story.isYourStory) {
        self.usernameLabel.text = @"Your Story";
        self.ringView.image = nil;
        self.ringView.layer.borderWidth = 1.0;
        self.ringView.layer.borderColor = [[IrisTheme sharedTheme] dividerColor].CGColor;
        self.ringView.layer.cornerRadius = self.ringView.bounds.size.width / 2.0;
        self.plusBadge.hidden = NO;
    } else {
        self.usernameLabel.text = story.username;
        self.plusBadge.hidden = YES;
        self.ringView.layer.borderWidth = 0;
        
        if (!story.viewed) {
            // Radiant violet-pink gradient ring for unread
            self.ringView.image = [IrisTheme gradientRingImageWithSize:self.ringView.bounds.size strokeWidth:2.5];
        } else {
            // Muted border for viewed
            self.ringView.image = nil;
            self.ringView.layer.borderWidth = 1.0;
            self.ringView.layer.borderColor = [[IrisTheme sharedTheme] dividerColor].CGColor;
            self.ringView.layer.cornerRadius = self.ringView.bounds.size.width / 2.0;
        }
    }
    
    // Offline safe procedural photographic avatar
    self.avatarImageView.image = [IrisData imageForKey:story.avatar
                                                  size:self.avatarImageView.bounds.size
                                                 title:[story.username uppercaseString]
                                              subtitle:@""];
    
    [self updateTheme];
}

- (void)updateTheme {
    self.plusBadge.layer.borderColor = [[IrisTheme sharedTheme] mainBackgroundColor].CGColor;
    self.usernameLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
}

- (void)handleTap {
    if (self.tapHandler) {
        self.tapHandler(self.story);
    }
}

@end

@interface IrisStoriesHeaderView ()
@property (nonatomic, strong) UIScrollView *scrollView;
@property (nonatomic, strong) NSMutableArray<IrisStoryItemView *> *itemViews;
@property (nonatomic, strong) UIView *bottomDivider;
@end

@implementation IrisStoriesHeaderView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        _itemViews = [NSMutableArray array];
        [self setupSubviews];
    }
    return self;
}

- (void)setupSubviews {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    self.scrollView = [[UIScrollView alloc] initWithFrame:self.bounds];
    self.scrollView.showsHorizontalScrollIndicator = NO;
    self.scrollView.alwaysBounceHorizontal = YES;
    self.scrollView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self addSubview:self.scrollView];
    
    self.bottomDivider = [[UIView alloc] initWithFrame:CGRectMake(0, self.bounds.size.height - 0.5, self.bounds.size.width, 0.5)];
    self.bottomDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    self.bottomDivider.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    [self addSubview:self.bottomDivider];
    
    [self reloadStories];
}

- (void)reloadStories {
    for (UIView *v in self.itemViews) {
        [v removeFromSuperview];
    }
    [self.itemViews removeAllObjects];
    
    NSArray<IrisStory *> *stories = [IrisData sharedData].stories;
    CGFloat itemWidth = 76.0;
    CGFloat itemHeight = 98.0;
    CGFloat padLeft = 12.0;
    
    __weak typeof(self) weakSelf = self;
    for (NSInteger i = 0; i < (NSInteger)stories.count; i++) {
        IrisStory *s = stories[i];
        IrisStoryItemView *item = [[IrisStoryItemView alloc] initWithFrame:CGRectMake(padLeft + i * (itemWidth + 6), 6, itemWidth, itemHeight)];
        [item configureWithStory:s];
        item.tapHandler = ^(IrisStory *story) {
            if ([weakSelf.delegate respondsToSelector:@selector(storiesHeaderViewDidSelectStory:)]) {
                [weakSelf.delegate storiesHeaderViewDidSelectStory:story];
            }
        };
        [self.scrollView addSubview:item];
        [self.itemViews addObject:item];
    }
    
    CGFloat totalWidth = padLeft + stories.count * (itemWidth + 6) + padLeft;
    self.scrollView.contentSize = CGSizeMake(totalWidth, self.bounds.size.height);
}

- (void)updateTheme {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.bottomDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    for (IrisStoryItemView *item in self.itemViews) {
        [item updateTheme];
    }
}

@end
