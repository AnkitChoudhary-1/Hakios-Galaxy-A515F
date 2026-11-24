// IrisExploreViewController.m - Discovery screen with live search and dynamic grid
#import "IrisExploreViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisPostViewerViewController.h"
#import "IrisProfileViewController.h"

@interface IrisExploreGridItemView : UIView
@property (nonatomic, strong) IrisPost *post;
@property (nonatomic, strong) UIImageView *imageView;
@property (nonatomic, strong) UIView *videoBadge;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, copy) void (^tapHandler)(IrisPost *post);
- (void)configureWithPost:(IrisPost *)post isVideo:(BOOL)isVideo isFeatured:(BOOL)isFeatured;
@end

@implementation IrisExploreGridItemView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.layer.cornerRadius = 8.0;
        self.layer.masksToBounds = YES;
        self.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
        
        self.imageView = [[UIImageView alloc] initWithFrame:self.bounds];
        self.imageView.contentMode = UIViewContentModeScaleAspectFill;
        self.imageView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        self.imageView.layer.masksToBounds = YES;
        [self addSubview:self.imageView];
        
        // Video play badge
        self.videoBadge = [[UIView alloc] initWithFrame:CGRectMake(self.bounds.size.width - 28, 8, 20, 20)];
        self.videoBadge.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin | UIViewAutoresizingFlexibleBottomMargin;
        self.videoBadge.backgroundColor = [UIColor colorWithWhite:0 alpha:0.6];
        self.videoBadge.layer.cornerRadius = 10.0;
        
        UIImageView *playIcon = [[UIImageView alloc] initWithFrame:CGRectMake(5, 5, 10, 10)];
        playIcon.image = [IrisTheme iconNamed:@"play" size:CGSizeMake(10, 10) color:[UIColor whiteColor] filled:YES];
        [self.videoBadge addSubview:playIcon];
        [self addSubview:self.videoBadge];
        self.videoBadge.hidden = YES;
        
        // Subtle caption overlay at bottom
        self.titleLabel = [[UILabel alloc] initWithFrame:CGRectMake(8, self.bounds.size.height - 24, self.bounds.size.width - 16, 16)];
        self.titleLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
        self.titleLabel.font = [UIFont systemFontOfSize:10 weight:UIFontWeightMedium];
        self.titleLabel.textColor = [UIColor whiteColor];
        self.titleLabel.shadowColor = [UIColor colorWithWhite:0 alpha:0.8];
        self.titleLabel.shadowOffset = CGSizeMake(0, 1);
        [self addSubview:self.titleLabel];
        
        UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleTap)];
        [self addGestureRecognizer:tap];
        self.userInteractionEnabled = YES;
    }
    return self;
}

- (void)configureWithPost:(IrisPost *)post isVideo:(BOOL)isVideo isFeatured:(BOOL)isFeatured {
    _post = post;
    self.videoBadge.hidden = !isVideo;
    self.titleLabel.text = [NSString stringWithFormat:@"@%@", post.username];
    
    self.imageView.image = [IrisData imageForKey:post.imageKey
                                            size:self.bounds.size
                                           title:isFeatured ? post.location : @""
                                        subtitle:isFeatured ? post.username : @""];
}

- (void)handleTap {
    if (self.tapHandler) {
        self.tapHandler(self.post);
    }
}

@end

@interface IrisExploreViewController () <UIScrollViewDelegate, UITextFieldDelegate>

@property (nonatomic, strong) UIView *headerView;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UIView *searchBarContainer;
@property (nonatomic, strong) UIImageView *searchIconView;
@property (nonatomic, strong) UITextField *searchTextField;
@property (nonatomic, strong) UIButton *clearButton;
@property (nonatomic, strong) UIScrollView *scrollView;
@property (nonatomic, strong) UIView *gridContainer;
@property (nonatomic, strong) NSMutableArray<IrisExploreGridItemView *> *gridItems;
@property (nonatomic, strong) UILabel *noResultsLabel;
@property (nonatomic, strong) NSArray<IrisPost *> *displayedPosts;

@end

@implementation IrisExploreViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.gridItems = [NSMutableArray array];
    self.displayedPosts = [IrisData sharedData].posts;
    
    [self setupHeaderAndSearch];
    [self setupScrollView];
    [self buildDynamicGrid];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.headerView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.searchBarContainer.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    self.searchTextField.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.searchIconView.image = [IrisTheme iconNamed:@"search" size:CGSizeMake(18, 18) color:[[IrisTheme sharedTheme] mutedTextColor] filled:NO];
    [self buildDynamicGrid];
}

- (void)setupHeaderAndSearch {
    CGFloat topSafe = 36.0;
    CGFloat headerH = topSafe + 88.0;
    
    self.headerView = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, headerH)];
    self.headerView.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.headerView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Title
    self.titleLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, topSafe, 140, 32)];
    self.titleLabel.text = @"Explore";
    self.titleLabel.font = [UIFont systemFontOfSize:26 weight:UIFontWeightBold];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.headerView addSubview:self.titleLabel];
    
    // Search bar container
    CGFloat searchY = topSafe + 38.0;
    CGFloat searchW = self.view.bounds.size.width - 32.0;
    self.searchBarContainer = [[UIView alloc] initWithFrame:CGRectMake(16, searchY, searchW, 40)];
    self.searchBarContainer.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.searchBarContainer.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    self.searchBarContainer.layer.cornerRadius = 10.0;
    self.searchBarContainer.layer.masksToBounds = YES;
    
    self.searchIconView = [[UIImageView alloc] initWithFrame:CGRectMake(12, 11, 18, 18)];
    self.searchIconView.image = [IrisTheme iconNamed:@"search" size:CGSizeMake(18, 18) color:[[IrisTheme sharedTheme] mutedTextColor] filled:NO];
    [self.searchBarContainer addSubview:self.searchIconView];
    
    self.searchTextField = [[UITextField alloc] initWithFrame:CGRectMake(38, 4, searchW - 76, 32)];
    self.searchTextField.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.searchTextField.font = [UIFont systemFontOfSize:14];
    self.searchTextField.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.searchTextField.placeholder = @"Search creators, captions, #tags...";
    self.searchTextField.returnKeyType = UIReturnKeySearch;
    self.searchTextField.clearButtonMode = UITextFieldViewModeWhileEditing;
    self.searchTextField.delegate = self;
    [self.searchTextField addTarget:self action:@selector(searchTextChanged:) forControlEvents:UIControlEventEditingChanged];
    [self.searchBarContainer addSubview:self.searchTextField];
    
    [self.headerView addSubview:self.searchBarContainer];
    [self.view addSubview:self.headerView];
}

- (void)setupScrollView {
    CGFloat topSafe = 36.0;
    CGFloat headerH = topSafe + 88.0;
    CGFloat bottomH = 64.0;
    
    self.scrollView = [[UIScrollView alloc] initWithFrame:CGRectMake(0, headerH, self.view.bounds.size.width, self.view.bounds.size.height - headerH - bottomH)];
    self.scrollView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.scrollView.backgroundColor = [UIColor clearColor];
    self.scrollView.delegate = self;
    self.scrollView.alwaysBounceVertical = YES;
    [self.view addSubview:self.scrollView];
    
    self.gridContainer = [[UIView alloc] initWithFrame:self.scrollView.bounds];
    self.gridContainer.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [self.scrollView addSubview:self.gridContainer];
    
    self.noResultsLabel = [[UILabel alloc] initWithFrame:CGRectMake(24, 60, self.view.bounds.size.width - 48, 40)];
    self.noResultsLabel.text = @"No results matching your query.";
    self.noResultsLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    self.noResultsLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightMedium];
    self.noResultsLabel.textAlignment = NSTextAlignmentCenter;
    self.noResultsLabel.hidden = YES;
    [self.scrollView addSubview:self.noResultsLabel];
}

- (void)searchTextChanged:(UITextField *)sender {
    NSString *query = [sender.text stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (query.length == 0) {
        self.displayedPosts = [IrisData sharedData].posts;
    } else {
        self.displayedPosts = [[IrisData sharedData] searchPostsWithQuery:query];
    }
    [self buildDynamicGrid];
}

- (BOOL)textFieldShouldReturn:(UITextField *)textField {
    [textField resignFirstResponder];
    return YES;
}

- (void)buildDynamicGrid {
    for (UIView *v in self.gridItems) {
        [v removeFromSuperview];
    }
    [self.gridItems removeAllObjects];
    
    if (self.displayedPosts.count == 0) {
        self.noResultsLabel.hidden = NO;
        self.scrollView.contentSize = CGSizeMake(self.view.bounds.size.width, 200);
        return;
    }
    self.noResultsLabel.hidden = YES;
    
    CGFloat screenW = self.view.bounds.size.width;
    CGFloat pad = 8.0;
    CGFloat colW = (screenW - (pad * 3.0)) / 2.0; // 2 column dynamic magazine grid
    
    CGFloat col1Y = pad;
    CGFloat col2Y = pad;
    
    __weak typeof(self) weakSelf = self;
    for (NSInteger i = 0; i < (NSInteger)self.displayedPosts.count; i++) {
        IrisPost *p = self.displayedPosts[i];
        
        // Varied height pattern: Square (1.0), Portrait (1.3), Large Featured (spans 2 cols), Video card
        BOOL isFeatured = (i % 6 == 0 && col1Y == col2Y); // Wide featured card every 6 items
        BOOL isVideo = (i % 3 == 0);
        
        CGFloat itemW = isFeatured ? (screenW - pad * 2.0) : colW;
        CGFloat itemH = isFeatured ? (colW * 1.1) : (i % 2 == 0 ? colW * 1.3 : colW);
        
        CGFloat x = pad;
        CGFloat y = pad;
        
        if (isFeatured) {
            CGFloat maxY = MAX(col1Y, col2Y);
            x = pad;
            y = maxY;
            col1Y = y + itemH + pad;
            col2Y = col1Y;
        } else {
            if (col1Y <= col2Y) {
                x = pad;
                y = col1Y;
                col1Y += itemH + pad;
            } else {
                x = pad * 2.0 + colW;
                y = col2Y;
                col2Y += itemH + pad;
            }
        }
        
        IrisExploreGridItemView *item = [[IrisExploreGridItemView alloc] initWithFrame:CGRectMake(x, y, itemW, itemH)];
        [item configureWithPost:p isVideo:isVideo isFeatured:isFeatured];
        item.tapHandler = ^(IrisPost *post) {
            IrisPostViewerViewController *viewer = [[IrisPostViewerViewController alloc] initWithPost:post];
            viewer.modalPresentationStyle = UIModalPresentationFullScreen;
            [weakSelf presentViewController:viewer animated:YES completion:nil];
        };
        
        [self.gridContainer addSubview:item];
        [self.gridItems addObject:item];
    }
    
    CGFloat totalH = MAX(col1Y, col2Y) + 20.0;
    self.gridContainer.frame = CGRectMake(0, 0, screenW, totalH);
    self.scrollView.contentSize = CGSizeMake(screenW, totalH);
}

@end
